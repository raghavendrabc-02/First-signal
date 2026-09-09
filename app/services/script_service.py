import asyncio

from app.services.ai_service import generate_ai_response


def build_script_prompt(article, research):
    prompt = f"""
You are a short-form content writer for a Kannada-speaking audience.

Create a natural, engaging Instagram Reel script from the article and research below.

Article:
{article.title}

Research:
{research}

Requirements:

- Maximum 50 seconds when spoken.

- Write mostly in natural spoken Kannada.

- Use English only for necessary names, products, companies, and technical terms.

- Start with a powerful curiosity-driven hook in the first sentence.

- Follow this structure: Hook → What happened → Most interesting details → Why it matters → Strong ending.

- Make it sound like a creator explaining the story to a friend, not like a newsreader.

- Keep sentences short and easy to speak.

- Focus only on the most interesting and relevant facts.

- Prefer 3 to 4 key facts rather than trying to include every detail.

- Include important numbers when they make the story stronger.

- Give the audience a clear reason to care.

- Do not invent or exaggerate information.

- Do not mention the research process.

- Do not use hashtags.

- Write as one natural spoken paragraph.

Return only the script.
"""
    return prompt

async def generate_script(article, research):
    prompt = build_script_prompt(article, research)

    script = await generate_ai_response(prompt)

    return script