"""REST API for introspecting the DSE MCP server capabilities.

Exposes the registered MCP tools, resource templates, and prompts so that
external systems (dashboard, agents) can discover what the MCP server offers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/v1/mcp", tags=["mcp"])


async def _get_mcp_server() -> Any:
    from dse.mcp.server import mcp

    return mcp


@router.get("")
async def list_mcp_capabilities() -> dict[str, Any]:
    """List all MCP capabilities: tools, resource templates, and prompts."""
    mcp = await _get_mcp_server()

    tools = await mcp.list_tools()
    resource_templates = await mcp.list_resource_templates()
    prompts = await mcp.list_prompts()

    return {
        "tools": [
            {
                "name": t.name,
                "description": (t.description or "").split("\n")[0],
            }
            for t in tools
        ],
        "resource_templates": [
            {
                "name": rt.name,
                "uri_template": rt.uriTemplate,
                "description": (rt.description or "").split("\n")[0],
            }
            for rt in resource_templates
        ],
        "prompts": [
            {
                "name": p.name,
                "description": (p.description or "").split("\n")[0],
                "arguments": [
                    {"name": a.name, "required": a.required} for a in (p.arguments or [])
                ],
            }
            for p in prompts
        ],
    }


@router.get("/tools")
async def list_mcp_tools() -> list[dict[str, Any]]:
    """List all MCP tools with their names, descriptions, and input schemas."""
    mcp = await _get_mcp_server()
    tools = await mcp.list_tools()

    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema,
        }
        for t in tools
    ]


@router.get("/tools/{tool_name}")
async def get_mcp_tool(tool_name: str) -> dict[str, Any]:
    """Get details for a specific MCP tool by name."""
    mcp = await _get_mcp_server()
    tools = await mcp.list_tools()

    for t in tools:
        if t.name == tool_name:
            return {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
                "output_schema": t.outputSchema,
                "annotations": t.annotations.model_dump() if t.annotations else None,
            }

    raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")


@router.get("/resources")
async def list_mcp_resources() -> list[dict[str, Any]]:
    """List all MCP resource templates."""
    mcp = await _get_mcp_server()
    templates = await mcp.list_resource_templates()

    return [
        {
            "name": rt.name,
            "uri_template": rt.uriTemplate,
            "description": rt.description or "",
            "mime_type": rt.mimeType,
        }
        for rt in templates
    ]


@router.get("/resources/{resource_name}")
async def get_mcp_resource(resource_name: str) -> dict[str, Any]:
    """Get details for a specific MCP resource template by name."""
    mcp = await _get_mcp_server()
    templates = await mcp.list_resource_templates()

    for rt in templates:
        if rt.name == resource_name:
            return {
                "name": rt.name,
                "uri_template": rt.uriTemplate,
                "description": rt.description or "",
                "mime_type": rt.mimeType,
                "annotations": rt.annotations.model_dump() if rt.annotations else None,
            }

    raise HTTPException(status_code=404, detail=f"Resource not found: {resource_name}")


@router.get("/prompts")
async def list_mcp_prompts() -> list[dict[str, Any]]:
    """List all MCP prompts."""
    mcp = await _get_mcp_server()
    prompts = await mcp.list_prompts()

    return [
        {
            "name": p.name,
            "description": p.description or "",
            "arguments": [{"name": a.name, "required": a.required} for a in (p.arguments or [])],
        }
        for p in prompts
    ]


@router.get("/prompts/{prompt_name}")
async def get_mcp_prompt(prompt_name: str) -> dict[str, Any]:
    """Get details for a specific MCP prompt by name."""
    mcp = await _get_mcp_server()
    prompts = await mcp.list_prompts()

    for p in prompts:
        if p.name == prompt_name:
            return {
                "name": p.name,
                "description": p.description or "",
                "arguments": [
                    {"name": a.name, "description": a.description, "required": a.required}
                    for a in (p.arguments or [])
                ],
            }

    raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_name}")
