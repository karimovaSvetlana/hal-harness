from litellm import completion
from pprint import pprint
from gigachat_model import *

model_name = "GigaChat:2.0.28.02"
# print(litellm.supports_function_calling(model=f"gigachat/{model_name}"))
resp = completion(
    model=f"gigachat/{model_name}",
    messages=[{"role": "user", "content": "Hello world!"}],
)
# print(resp)
# pprint(litellm.get_llm_provider(f"gigachat/{model_name}"))
# print(litellm.cost_calculator.completion_cost(resp))
# print(resp)

# pprint(litellm.model_cost.get(f"gigachat/{model_name}", {}))