import asyncio
import logging
import sys

print("S1")
async def main():
    print("S2")
    await asyncio.sleep(1)
    print("S3")

if __name__ == "__main__":
    print("S0")
    asyncio.run(main())
