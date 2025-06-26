import os
import time
import json
import yaml
from typing import Optional, List, Dict, Any

import litellm
from litellm import CustomLLM, completion, get_llm_provider, ModelResponse, Choices, Message, Usage
from gigachat import GigaChat

from config import load_config
config = load_config("/home/sveta/hal-harness/config.yaml") # используется только как дефольный параметр в register_config


class BaseGigaChatLLM(CustomLLM):
    """Базовый класс для работы с GigaChat через LiteLLM"""
    
    def __init__(self, config):
        """
        Инициализация модели GigaChat
        
        :param config: Конфигурация модели из YAML
        """
        super().__init__()
        self._load_config(config)
        self.llm = self._init_gigachat()
        
    def _load_config(self, config) -> None:
        """Загрузка конфигурации модели"""
        model_config = config.model
        
        self.model_name = model_config.name

        self.api_token = model_config.api.token
        self.base_url = model_config.api.url

        self.scope = model_config.parameters.scope
        # self.temperature = model_config.parameters.temperature
        # self.max_tokens = model_config.parameters.max_tokens
        # self.top_p = model_config.parameters.top_p
        self.profanity_check = model_config.parameters.profanity_check
        self.timeout = model_config.parameters.timeout
        self.max_retries = model_config.parameters.max_retries

    def _init_gigachat(self) -> GigaChat:
        """Инициализация клиента GigaChat"""
        print("A"*50, self.base_url)
        giga_kwargs = dict(
            model=self.model_name,
            base_url=self.base_url,
            scope=self.scope,
            verify_ssl_certs=False,
            profanity_check=self.profanity_check,
            timeout=self.timeout,
        )
        try:
            client = GigaChat(
                credentials=os.environ.get("GIGACHAT_CREDENTIALS"),
                access_token=self.api_token,
                **giga_kwargs,
            )
        except Exception:
            client = GigaChat(
                credentials=self.api_token,
                **giga_kwargs,
            )
        return client
    
    def _create_model_response(self, response: Any, tool_calls: Optional[List] = None) -> ModelResponse:
        """Создание объекта ModelResponse для LiteLLM"""
        message = Message(
            role=response.choices[-1].message.role,
            content=response.choices[-1].message.content,
            tool_calls=tool_calls,
            provider_specific_fields=None
        )

        return ModelResponse(
            id=response.x_headers["x-request-id"],
            created=response.created,
            model=response.model,
            object=response.object_,
            choices=[Choices(
                index=response.choices[-1].index, 
                message=message, 
                finish_reason=response.choices[-1].finish_reason
            )],
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
        )
    
    def _retry_completion(self, request_data: Dict[str, Any]) -> Any:
        """Повторные попытки выполнения запроса с экспоненциальной задержкой"""
        for i in range(self.max_retries):
            try:
                return self.llm.chat(request_data)
            except Exception as e:
                print(f"Attempt {i+1} failed: {type(e)} - {e}")
                time.sleep(5 * (i + 1))
        raise Exception(f"Failed after {self.max_retries} retries")


class GigaChatCustomLLM(BaseGigaChatLLM):
    """Модель для агента с поддержкой функций"""
    
    def __init__(self, config):
        super().__init__(config)

    def _process_tool_content(self, content: str) -> str:
        """Обработка содержимого tool-сообщения"""
        if isinstance(content, str):   # проверяем, есть ли у функции ответ (строка со словарем внутри, пустые строки или просто строки гига не вспринимает)
            try:
                json.loads(content)
                return content
            except (json.JSONDecodeError, TypeError):
                return json.dumps({"result": content})
        return json.dumps(content)

    def _process_tool_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Обработка сообщений с tool_calls для GigaChat"""
        processed_messages = []
        
        for i, m in enumerate(messages):  # корректируем messages для гиги
            if "tool_calls" in m:    # меняем tool_calls на function_call и записываем в него запрос к функции и ответ от функции
                tool_calls = m.pop("tool_calls")
                tc_func = tool_calls[0].get("function")
                
                if isinstance(tc_func.get("arguments"), str):
                    try:
                        tc_func["arguments"] = json.loads(tc_func.get("arguments"))
                    except (json.JSONDecodeError, TypeError):
                        tc_func["arguments"] = tc_func.get("arguments")

                processed_messages.append({
                    "function_call": tc_func,
                    "functions_state_id": tool_calls[0].get("id"),
                    "content": messages[i+1]["content"],
                    "role": m["role"]
                })
            elif m.get("role") == "tool":  # добавляем ответ функции в историю чата          
                m_content = self._process_tool_content(m["content"])
                processed_messages.append({
                    "role": "function",
                    "content": m_content,
                    "name": m["name"],
                })
            else:
                processed_messages.append(m)
                
        return processed_messages
    
    def _prepare_tool_calls(self, response: Any) -> Optional[List[Dict[str, Any]]]:
        """Подготовка tool_calls для ответа"""
        if not hasattr(response.choices[-1].message, 'function_call'):
            return None

        fc = response.choices[-1].message.function_call
        if fc is None:
            return None

        return [{
            "function": {
                "arguments": json.dumps(fc.arguments),
                "name": fc.name
            }
        }]

    def completion(self, *args, **kwargs) -> ModelResponse:
        """Обработка запроса с функциями"""
        messages = kwargs.get("messages", [])
        functions = kwargs.get("optional_params", {}).get("tools", [])
        
        processed_messages = self._process_tool_messages(messages)
        
        request_data = {
            "messages": processed_messages,
            "function_call": "auto",
            "functions": [func["function"] for func in functions],
        }
        
        response = self._retry_completion(request_data)
        tool_calls = self._prepare_tool_calls(response)
        
        return self._create_model_response(response, tool_calls)


def register_models(config=config) -> None:
    """Регистрация моделей в LiteLLM"""
    gigachat_custom_llm = GigaChatCustomLLM(config)

    litellm.custom_provider_map = [
        {"provider": "gigachat", "custom_handler": gigachat_custom_llm}
    ]

    resp = completion(
        model=f"gigachat/{config.model.name}",
        messages=[{"role": "user", "content": "Hello world!"}],
        input_cost_per_second=0.0,
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
    )
