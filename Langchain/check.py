# import sys
# print("Python executable:", sys.executable)

# try:
#     import langchain_google_genai
#     print("langchain_google_genai module FOUND")
# except ModuleNotFoundError:
#     print("langchain_google_genai module NOT found")

# import pip
# for dist in pip.get_installed_distributions():
#     if 'langchain-google-genai' in dist.project_name:
#         print(f"Installed package: {dist.project_name} {dist.version}")
# import platform
# print(platform.platform())


# import sys
# import os
# import streamlit as st

# print("Python executable:", sys.executable)
# print("sys.path:", sys.path)

import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

for m in genai.list_models():
    print(m.name, m.supported_generation_methods)