import os
import json
import logging
from typing import List, Union, Dict, Any, Optional
from langchain_core.tools import BaseTool
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)
load_dotenv()


class ModelContextProtocolServer:

    def __init__(self):
        self._client_cache: Dict[str, MultiServerMCPClient] = {}
        self._register_default_servers()

    def _register_default_servers(self):
        mcp_servers = os.getenv("DEFAULT_MCP_SERVERS")
        if mcp_servers:
            try:
                configs = json.loads(mcp_servers)
                for name, config in configs.items():
                    self._client_cache[name] = MultiServerMCPClient({f"{name}": config})
                    logger.info(f"_register_mcp_servers: {name}, url {config.get('url')}")
            except json.JSONDecodeError:
                logger.error(f" register_default_servers Failed to parse {mcp_servers}")

    def get_client(self, tool_name: Optional[str] = None) -> Optional[MultiServerMCPClient]:
        if self._client_cache and tool_name:
            return self._client_cache.get(tool_name)

    async def get_tools(self, tool_name: Optional[str] = None) -> Optional[list[BaseTool]]:
        client = self.get_client(tool_name)
        if client:
            return await client.get_tools()

mcp_server = ModelContextProtocolServer()



