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


# class GigaChatUserLLM(CustomLLM):
#     def __init__(self):
#         super().__init__()
#         self.model_name = model_name  # HARD
#         kwargs_giga = dict(
#             model=self.model_name,
#             base_url=base_url,
#             credentials=os.environ.get("GIGACHAT_CREDENTIALS", None),
#             access_token=os.getenv("GIGACHAT_TOKEN"),
#             scope=os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_CORP"),
#             verify_ssl_certs=False,
#             profanity_check=False,
#             timeout=600,
#         )
#         self.llm = GigaChat(**kwargs_giga)

#     def completion(self, *args, **kwargs) -> litellm.ModelResponse:
#         # print("User")
#         messages = kwargs.get("messages", [])
#         i, max_retries = 0, 20
#         while i < max_retries:
#             try:
#                 response = self.llm.chat({"messages": messages})
#                 break
#             except Exception as e:
#                 print(type(e), e)
#                 time.sleep(5)
#             i += 1

#         message = Message(
#             role=response.choices[-1].message.role,
#             content=response.choices[-1].message.content,
#             provider_specific_fields=None
#         )

#         model_response = ModelResponse(
#             id=response.x_headers["x-request-id"],
#             created=response.created,
#             model=response.model,
#             object=response.object_,
#             choices=[Choices(index=response.choices[-1].index, message=message, finish_reason=response.choices[-1].finish_reason)],
#             usage=Usage(
#                 prompt_tokens=response.usage.prompt_tokens,
#                 completion_tokens=response.usage.completion_tokens,
#                 total_tokens=response.usage.total_tokens,
#             ),
#         )
#         return model_response


class GigaChatCustomLLM(CustomLLM):
    def __init__(self):
        super().__init__()
        self.model_name = model_name  # HARD
        kwargs_giga = dict(
            model=self.model_name,
            base_url=base_url,
            credentials=os.environ.get("GIGACHAT_CREDENTIALS", None),
            access_token=os.getenv("GIGACHAT_TOKEN"),
            scope=os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_CORP"),
            verify_ssl_certs=False,
            profanity_check=False,
            timeout=600,
        )
        self.llm = GigaChat(**kwargs_giga)

    def completion(self, *args, **kwargs) -> litellm.ModelResponse:
        # print("NoUser")
        messages = kwargs.get("messages", [])
        functions = kwargs.get("optional_params", {}).get("tools", [])

        for i, m in enumerate(messages):  # корректируем messages для гиги

            if "tool_calls" in m:  # меняем tool_calls на function_call и записываем в него запрос к функции и ответ от функции
                tool_calls = messages[i].pop("tool_calls")

                tc_func = tool_calls[0].get("function")
                if isinstance(tc_func.get("arguments"), str):
                    try:
                        tc_func["arguments"] = json.loads(tc_func.get("arguments"))
                    except (json.JSONDecodeError, TypeError):
                        tc_func["arguments"] = tc_func.get("arguments")

                messages[i] = {
                    "function_call": tc_func,
                    "functions_state_id": tool_calls[0].get("id"),
                    "content": messages[i+1]["content"],
                    "role": messages[i]["role"]
                }

            if m.get("role") == "tool":  # добавляем ответ функции в историю чата
                if isinstance(m["content"], str):  # проверяем, есть ли у функции ответ (строка со словарем внутри, пустые строки или просто строки гига не вспринимает)
                    try:
                        m_content = json.loads(m["content"])
                        m_content = m["content"]
                    except (json.JSONDecodeError, TypeError):
                        m_content = json.dumps({"result": m["content"]})

                messages[i] = {
                    "role": "function",
                    "content": m_content,
                    "name": messages[i]["name"],
                }


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
# gigachat_user_llm = GigaChatUserLLM()

litellm.custom_provider_map = [ # 👈 KEY STEP - REGISTER HANDLER
    # {"provider": "gigachat_user", "custom_handler": gigachat_user_llm},
    {"provider": "gigachat", "custom_handler": gigachat_custom_llm}
]


# resp = completion(
#     model=f"gigachat_user/{model_name}",
#     messages=[{"role": "user", "content": "Hello world!"}],
#     # отвечает за регистрацию стоимости генерации модели, если еще input_cost_per_token и output_cost_per_token
#     # без него по дефолту res._hidden_params["response_cost"] = None (res = completion(...)), и ошибка "couldnt add None and 0.0"
#     input_cost_per_second=0.0
# )
resp = completion(
    model=f"gigachat/{model_name}",
    messages=[{"role": "user", "content": "Hello world!"}],
    # отвечает за регистрацию стоимости генерации модели, если еще input_cost_per_token и output_cost_per_token
    # без него по дефолту res._hidden_params["response_cost"] = None (res = completion(...)), и ошибка "couldnt add None and 0.0"
    input_cost_per_second=0.0
)
