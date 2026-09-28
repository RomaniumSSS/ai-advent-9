"""Каталог двух MCP-серверов и проверенная адресация tool call."""
from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

from jsonschema import Draft202012Validator, FormatChecker
from mcp import Client, StdioServerParameters

from .config import MAX_ARGS_BYTES, MAX_RESULT_BYTES
from .store import compact


class McpBoundaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class McpConfig:
    server: str
    command: str
    args: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    env: dict[str, str] | None = None

    def parameters(self) -> StdioServerParameters:
        return StdioServerParameters(command=self.command, args=list(self.args), env=self.env)


@dataclass(frozen=True)
class ToolRoute:
    alias: str
    original: str
    config: McpConfig
    schema: dict
    description: str


async def _discover(config: McpConfig) -> list[dict]:
    async with asyncio.timeout(45):
        async with Client(config.parameters()) as client:
            found=[]; cursor=None; cursors=set()
            while True:
                page=await client.list_tools(cursor=cursor)
                found.extend({"name":tool.name,"description":tool.description or "",
                              "schema":dict(tool.input_schema)} for tool in page.tools)
                cursor=page.next_cursor
                if cursor is None:
                    return found
                if cursor in cursors:
                    raise McpBoundaryError("discovery_pagination")
                cursors.add(cursor)


def discover(config: McpConfig) -> list[dict]:
    try:
        return asyncio.run(_discover(config))
    except Exception as error:
        raise McpBoundaryError(f"discovery_{config.server}") from error


def _normalise(result) -> dict:
    if result.is_error:
        raise McpBoundaryError("mcp_tool_error")
    structured=result.structured_content
    if structured is not None:
        if not isinstance(structured, dict):
            raise McpBoundaryError("mcp_structured_type")
        answer=dict(structured)
    else:
        blocks=[]
        for block in result.content:
            kind=getattr(block,"type",None)
            if kind=="text":
                blocks.append({"type":"text","text":block.text})
            elif kind=="resource":
                resource=block.resource
                if not isinstance(getattr(resource,"text",None),str):
                    raise McpBoundaryError("mcp_resource_type")
                blocks.append({"type":"resource","uri":resource.uri,
                               "mime_type":resource.mime_type,"text":resource.text})
            elif kind=="resource_link":
                blocks.append({"type":"resource_link","uri":block.uri,
                               "name":block.name,"description":block.description})
            else:
                raise McpBoundaryError("mcp_content_type")
        if not blocks:
            raise McpBoundaryError("mcp_empty_result")
        answer={"status":"ok","blocks":blocks}
    if len(compact(answer).encode("utf-8")) > MAX_RESULT_BYTES:
        raise McpBoundaryError("mcp_result_too_large")
    return answer


async def _execute(route: ToolRoute, args: dict) -> dict:
    async with asyncio.timeout(45):
        async with Client(route.config.parameters()) as client:
            result = await client.call_tool(route.original,args)
    return _normalise(result)


class Router:
    def __init__(self, configs: tuple[McpConfig, ...]):
        if len(configs)<2 or len({c.server for c in configs})!=len(configs):
            raise ValueError("two_distinct_servers_required")
        self.configs=configs
        self.routes: dict[str,ToolRoute]={}
        self._public_repos: set[tuple[str,str]]=set()

    def _require_public_repo(self, args: dict) -> None:
        owner,repo=args.get("owner"),args.get("repo")
        pattern=r"[A-Za-z0-9_.-]{1,100}"
        if not isinstance(owner,str) or not isinstance(repo,str) or not re.fullmatch(pattern,owner) or not re.fullmatch(pattern,repo):
            raise McpBoundaryError("github_repo_invalid")
        key=(owner.casefold(),repo.casefold())
        if key in self._public_repos:
            return
        url="https://api.github.com/repos/"+urllib.parse.quote(owner)+"/"+urllib.parse.quote(repo)
        request=urllib.request.Request(url,headers={"Accept":"application/vnd.github+json",
                                                    "User-Agent":"day20-public-repo-guard/1"})
        try:
            with urllib.request.urlopen(request,timeout=8) as response:
                if response.status!=200:
                    raise McpBoundaryError("github_repo_unconfirmed_public")
                metadata=json.load(response)
        except Exception as error:
            raise McpBoundaryError("github_repo_unconfirmed_public") from error
        if metadata.get("private") is not False or metadata.get("full_name","").casefold()!=f"{owner}/{repo}".casefold():
            raise McpBoundaryError("github_repo_unconfirmed_public")
        self._public_repos.add(key)

    def refresh(self) -> list[dict]:
        routes={}
        for config in self.configs:
            raw=discover(config)
            names={item["name"] for item in raw}
            if not set(config.allowed_tools).issubset(names):
                raise McpBoundaryError(f"catalog_missing_{config.server}")
            for item in raw:
                if item["name"] not in config.allowed_tools:
                    continue
                alias=f"{config.server}__{item['name']}"
                if alias in routes:
                    raise McpBoundaryError("tool_alias_collision")
                Draft202012Validator.check_schema(item["schema"])
                routes[alias]=ToolRoute(alias,item["name"],config,item["schema"],item["description"])
        self.routes=routes
        return self.model_tools()

    def model_tools(self) -> list[dict]:
        return [{"type":"function","function":{"name":route.alias,
                "description":route.description,"parameters":route.schema}}
                for route in self.routes.values()]

    def execute(self, alias: str, raw_args: str) -> dict:
        route=self.routes.get(alias)
        if route is None:
            raise McpBoundaryError("tool_not_allowed")
        if not isinstance(raw_args,str) or len(raw_args.encode("utf-8"))>MAX_ARGS_BYTES:
            raise McpBoundaryError("invalid_arguments")
        try:
            args=json.loads(raw_args)
        except (TypeError,ValueError) as error:
            raise McpBoundaryError("invalid_json") from error
        if not isinstance(args,dict):
            raise McpBoundaryError("schema_violation")
        errors=list(Draft202012Validator(route.schema,format_checker=FormatChecker()).iter_errors(args))
        if errors:
            raise McpBoundaryError("schema_violation")
        if route.config.server=="github":
            self._require_public_repo(args)
        try:
            return asyncio.run(_execute(route,args))
        except McpBoundaryError:
            raise
        except Exception as error:
            raise McpBoundaryError("mcp_execution_error") from error
