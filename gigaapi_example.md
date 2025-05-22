```python
# Disclaimer: this is not a functional agent and is only for demonstration purposes. This implementation is just a single model call.
# from openai import OpenAI
import gigachat
from gigachat import GigaChat
import os 

base_url = "https://gigachat.ift.sberdevices.ru/v1"
scope = "GIGACHAT_API_CORP"

def run(input: dict[str, dict], **kwargs) -> dict[str, str]:

    assert 'model_name' in kwargs, 'model_name is required'
    assert len(input) == 1, 'input must contain only one task'
    
    task_id, task = list(input.items())[0]
    
    client = gigachat.GigaChat(
        base_url=base_url,
        credentials=os.environ.get("GIGACHAT_CREDENTIALS", None),
        access_token=os.environ.get("GIGACHAT_TOKEN", None),
        scope=os.environ.get("GIGACHAT_SCOPE", scope),
        verify_ssl_certs=False,
        timeout=200,
    )

    results = {}


    payload = gigachat.models.Chat(
        messages=[
            {"role": "user", "content": "Solve the following problem: " + task['problem_statement']},
        ],
        model=kwargs['model_name'],
        max_tokens=64,
        temperature=0.0,
        **kwargs,
    )

    response = client.chat(payload).choices[0].message.content

    # response = client.chat.completions.create(
    #     model=kwargs['model_name'],
    #     messages=[
    #         {"role": "user", "content": "Solve the following problem: " + task['problem_statement']},
    #         ],
    #     max_tokens=2000,
    #     n=1,
    #     temperature=1,
    # )
    # results[task_id] = response.choices[0].message.content
    
    results[task_id] = response
        
    return results
```