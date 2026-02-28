import asyncio
from google import genai
from config import settings


async def main():
    print("Listing models...")
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        # Try waiting for list then iterating
        pager = await client.aio.models.list()
        print(f"Pager type: {type(pager)}")
        # It's likely an AsyncPager or similar
        async for m in pager:
            print(f"Model: {m.name}")
            if "generateContent" in m.supported_generation_methods:
                print(f" - supports generateContent")
    except Exception as e:
        print(f"List failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
