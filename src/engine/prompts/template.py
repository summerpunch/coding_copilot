import os
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)

def get_local_prompt(prompt_name: str) -> Optional[str]:
    logger.info(f"使用本地提示词文件: {prompt_name}.md")
    template = env.get_template(f"{prompt_name}.md")
    return template.render()
