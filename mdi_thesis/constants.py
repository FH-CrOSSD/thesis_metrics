"""
Module to store confidental information.
Includes API Token.
"""
import os
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.environ.get("GH_TOKEN").strip()
