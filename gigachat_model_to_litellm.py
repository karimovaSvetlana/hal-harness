import os
from datetime import datetime
import uuid
import json
import time

import litellm
from litellm import CustomLLM, completion, get_llm_provider, ModelResponse, Choices, Message, Usage
from gigachat import GigaChat
from pprint import pprint

model_name = "GigaChat:2.0.28.02"
base_url = "https://gigachat.ift.sberdevices.ru/v1"


def normalize_messages(messages):  # корректируем messages для гиги 
    normalized = []
    for m in messages:
        # Копируем сообщение, чтобы не изменять оригинал
        message = m.copy()
        
        # Обрабатываем content, если он не строка
        if not isinstance(message['content'], str):
            if isinstance(message['content'], list):
                # Ищем первый элемент с полем 'text' (если content - список)
                for item in message['content']:
                    if isinstance(item, dict) and 'text' in item:
                        message['content'] = item['text']
                        break
                else:
                    # Если не нашли text, преобразуем весь content в строку
                    message['content'] = str(message['content'])
            elif isinstance(message['content'], dict):
                # Если content - словарь, ищем поле 'text'
                message['content'] = message['content'].get('text', str(message['content']))
            else:
                # Для других типов просто преобразуем в строку
                message['content'] = str(message['content'])
        
        # Обрабатываем tool_calls (в гиге это function_call)
        if "tool_calls" in message:  # меняем tool_calls на function_call и записываем в него запрос к функции и ответ от функции
            tool_calls = message.pop("tool_calls")
            tc_func = tool_calls[0].get("function")
            
            if isinstance(tc_func.get("arguments"), str):
                try:
                    tc_func["arguments"] = json.loads(tc_func.get("arguments"))
                except (json.JSONDecodeError, TypeError):
                    tc_func["arguments"] = tc_func.get("arguments")
            
            message = {
                "function_call": tc_func,
                "functions_state_id": tool_calls[0].get("id"),
                "content": message['content'],  # Используем уже нормализованный content
                "role": message["role"]
            }
        
        # Обрабатываем role=tool
        # добавляем ответ функции в историю чата
        # проверяем, есть ли у функции ответ (строка со словарем внутри, пустые строки или просто строки гига не воспринимает)
        if message.get("role") == "tool":  
            content = message["content"]
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                    content = message["content"]  # Сохраняем оригинал, если он JSON
                except (json.JSONDecodeError, TypeError):
                    content = json.dumps({"result": message["content"]})
            
            message = {
                "role": "function",
                "content": content,
                "name": message.get("name", ""),
            }
        
        normalized.append(message)
    
    return normalized


class GigaChatCustomLLM(CustomLLM):
    def __init__(self):
        super().__init__()
        self.model_name = model_name  # HARD
        kwargs_giga = dict(
            model=self.model_name,
            base_url=base_url,
            credentials=os.environ.get("GIGACHAT_CREDENTIALS", None),
            access_token="eyJhbGciOiJkaXIiLCJlbmMiOiJBMTI4R0NNIiwidHlwIjoiSldUIn0..6dYlsXHw3xm43TDF.Orn5OV6fpd45Qaf7fj5s8UebkuaveJw1W3IS3NFgGkYTzMfBTSqdqSNLLKdYzrkZtgCLv7-arZjnY7g.T_p0mh3IBf2vlyV-jeZWiw", #os.getenv("GIGACHAT_TOKEN"),
            scope=os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_CORP"),
            verify_ssl_certs=False,
            profanity_check=False,
            timeout=600,
        )
        self.llm = GigaChat(**kwargs_giga)

    def completion(self, *args, **kwargs) -> litellm.ModelResponse:
        messages = kwargs.get("messages", [])
        functions = kwargs.get("optional_params", {}).get("tools", [])

        messages = normalize_messages(messages)

        function_call_json  = {
            "messages": messages,
            "function_call": "auto",
            "functions": [func["function"] for func in functions],
        }
        i, max_retries = 0, 5
        while i < max_retries:
            try:
                response = self.llm.chat(function_call_json)
                break
            except Exception as e:
                print(type(e), e)
                time.sleep(5)
            i += 1

        fc = response.choices[-1].message.function_call
        message = Message(
            role=response.choices[-1].message.role,
            content=response.choices[-1].message.content,
            tool_calls=fc if fc is None else [{"function": {"arguments": json.dumps(fc.arguments), "name": fc.name}}],
            provider_specific_fields=None
        )

        model_response = ModelResponse(
            id=response.x_headers["x-request-id"],
            created=response.created,
            model=response.model,
            object=response.object_,
            choices=[Choices(index=response.choices[-1].index, message=message, finish_reason=response.choices[-1].finish_reason)],
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
        )

        return model_response


gigachat_custom_llm = GigaChatCustomLLM()

litellm.custom_provider_map = [ # 👈 KEY STEP - REGISTER HANDLER
    {"provider": "gigachat", "custom_handler": gigachat_custom_llm}
]

# resp = completion(
#     model=f"gigachat/{model_name}",
#     messages=[{"role": "user", "content": "Hello world!"}],
#     input_cost_per_second=0.0,
#     input_cost_per_token=0.0,
#     output_cost_per_token=0.0,
# )