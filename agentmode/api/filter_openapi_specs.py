from asyncio import Semaphore, gather
from dataclasses import dataclass

import litellm

PROMPT = """Determine if the following API call is something that a software engineer would use as part of their regular software development lifecycle
involving planning, application development, Git, code reviews, testing / debugging, performance monitoring, security, and deployment / infrastructure.
For example, API calls related to IT administration, user management, billing, or other non-development tasks should be excluded, as well as any API calls that would only rarely be needed.
If it is relevant to the software development lifecycle, return 'true', otherwise return 'false'.

API call: {api_call}
"""

SEARCH_PROMPT = """
Determine if the following API call is related to searching or viewing specific search results, for something that a software engineer would use as part of their regular software development lifecycle.
If it is relevant, return 'true', otherwise return 'false'.

API call: {api_call}
"""

MAX_CONCURRENT_CALLS = 5
LLM_MODEL = "gpt-4.1-nano"  # or "gemini/gemini-2.0-flash"
# set your OpenAI or Google Gemini API key in the environment variables OPENAI_API_KEY or GEMINI_API_KEY

@dataclass
class FilterOpenAPISpecs:
    """
    Filter an OpenAPI specification to only include
    the API calls that are relevant to software engineers, to 
    ensure that only necessary endpoints are processed.
    """
    name: str

    async def filter_api_calls(self, api_calls):
        """
        for each api call, call filter_api_call in parallel
        with a rate limit of 5 concurrent calls
        """
        semaphore = Semaphore(MAX_CONCURRENT_CALLS)

        async def limited_filter(api_call):
            async with semaphore:
                return await self.filter_api_call(api_call)

        tasks = [limited_filter(api_call) for api_call in api_calls]
        results = await gather(*tasks)
        # Filter the API calls based on the results
        filtered_api_calls = [api_call for api_call, result in zip(api_calls, results) if result]
        return filtered_api_calls

    async def filter_api_call(self, api):
        """
        Filter the API call to only include relevant information.
        """
        api_call = f"API for: {self.name}\n"
        relevant_keys = [
            'url',
            'method',
            'parameters',
            'description',
            'tags'
        ]
        for key in relevant_keys:
            if key in api:
                api_call += f"{key}: {api[key]}\n"
        # Format the prompt
        prompt = PROMPT.format(api_call=api_call)

        model_args = {}
        response = await litellm.acompletion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response['choices'][0]['message']['content']
        return True if result.lower() == 'true' else False