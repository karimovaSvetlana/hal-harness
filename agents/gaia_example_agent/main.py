# Disclaimer: this is not a functional agent and is only for demonstration purposes. This implementation is just a single model call.
import os
# from gigachat import GigaChat

kwargs_giga = dict(
    model="GigaChat:2.0.28.02",
    base_url="https://gigachat.ift.sberdevices.ru/v1",
    credentials=os.environ.get("GIGACHAT_CREDENTIALS"),
    access_token=os.environ.get("GIGACHAT_TOKEN"),
    scope="GIGACHAT_API_CORP",
    verify_ssl_certs=False,
    profanity_check=False,
    timeout=600,
    max_tokens=128_000,
)

# def run(input: dict[str, dict], **kwargs) -> dict[str, str]:

#     assert 'model_name' in kwargs, 'model_name is required'
#     assert len(input) == 1, 'input must contain only one task'
    
#     task_id, task = list(input.items())[0]
    
#     llm = GigaChat(**kwargs_giga)

#     results = {}
    
#     prompt = f"""Please answer the question below. You should:                                                                                                                   
                                                                                                                                                                 
# - Return only your answer, which should be a number, or a short phrase with as few words as possible, or a comma separated list of numbers and/or strings.      
# - If the answer is a number, return only the number without any units unless specified otherwise.                                                               
# - If the answer is a string, don't include articles, and don't use abbreviations (e.g. for states).                                                             
# - If the answer is a comma separated list, apply the above rules to each element in the list.                                                                                                                                                                                                                    
                                                                                                                                                                 
# Here is the question:

# {task['Question']}"""

#     response = llm.chat(prompt)
    
#     results[task_id] = response.choices[0].message.content
        
#     return results



# This is an example agent that uses smolagents to generate answers for the AssistantBench benchmark.
from langchain_gigachat.chat_models import GigaChat as GigaChat_langchain
from browser_use import Agent, Browser, BrowserConfig
import asyncio
import os
import warnings
import json
import time
from pydantic import PydanticDeprecatedSince20


base_url = "https://gigachat.ift.sberdevices.ru/v1"
class GigaChat(GigaChat_langchain):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = base_url
    
    def invoke(self, *args, **kwargs) -> str:
        i, max_retries = 0, 20
        while i <= max_retries:
            try:
                response = super().invoke(*args, **kwargs)
                return response
            except Exception as e:
                print(f"Exception occurred: {type(e)}, {e}")
            time.sleep(1)
            i += 1
        return "I can't answer this question"

    async def ainvoke(self, *args, **kwargs) -> str:
        i, max_retries = 0, 20
        while i <= max_retries:
            try:
                response = await super().ainvoke(*args, **kwargs)
                return response
            except Exception as e:
                print(f"Exception occurred: {type(e)}, {e}")
            time.sleep(1)
            i += 1
        return "I can't answer this question"
            


warnings.filterwarnings("ignore", category=DeprecationWarning)

warnings.filterwarnings(
    "ignore",
    category=PydanticDeprecatedSince20,
    message=r".*__fields__.*deprecated.*"
)
warnings.filterwarnings(
    "ignore",
    category=PydanticDeprecatedSince20,
    message=r".*__fields_set__.*deprecated.*"
)


def run(input: dict[str, dict], **kwargs) -> dict[str, str]:

    assert 'model_name' in kwargs, 'model_name is required'

    model_name = kwargs['model_name'].split('/')[-1]

    api_key = os.getenv("GIGACHAT_TOKEN")
    kwargs_giga = dict(
        model=kwargs['model_name'],
        base_url=base_url,
        credentials=os.environ.get("GIGACHAT_CREDENTIALS", None),
        access_token=api_key,
        scope=os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_CORP"),
        verify_ssl_certs=False,
        profanity_check=False,
        timeout=600,
        max_tokens=128_000,
    )
    llm = GigaChat(**kwargs_giga)
    planner_llm = GigaChat(**kwargs_giga)
    
    task_id = list(input.keys())[0]
    task_data = input[task_id]

    message_context = """\
Please answer the question below. You should:                                                                                                                   
                                                                                                                                                                 
- Return only your answer, which should be a number, or a short phrase with as few words as possible, or a comma separated list of numbers and/or strings.      
- If the answer is a number, return only the number without any units unless specified otherwise.                                                               
- If the answer is a string, don't include articles, and don't use abbreviations (e.g. for states).                                                             
- If the answer is a comma separated list, apply the above rules to each element in the list.                                                                                                                                                                                                                    
                                                                                                                                                                 
Here is the question:

"""
    question = task_data["Question"]

    async def _main():
        browser = Browser(
            config=BrowserConfig(headless=True)
        )
        agent = Agent(
            task=question,
            message_context=message_context,
            llm=llm,
            use_vision=False,
            planner_llm=planner_llm,
            use_vision_for_planner=False,
            planner_interval=2,
            browser=browser
        )
        try:
            result = await agent.run(max_steps=30)
        finally:
            await browser.close()
        return result
    
    run_result = asyncio.run(_main())
    answer = run_result.final_result()

    # if answer is null or empty, return empty string
    if answer is None:
        print("=-=-=-=-= answer =-=-=-=-=", answer)
        answer = ""
    
    return {task_id: answer}
