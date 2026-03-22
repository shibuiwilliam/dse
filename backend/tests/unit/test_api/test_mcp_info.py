from __future__ import annotations

from fastapi.testclient import TestClient

from dse.main import app

client = TestClient(app)


class TestListCapabilities:
    def test_list_all(self) -> None:
        resp = client.get("/v1/mcp")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "resource_templates" in data
        assert "prompts" in data
        assert len(data["tools"]) > 0
        # Each tool summary should have name and description
        tool = data["tools"][0]
        assert "name" in tool
        assert "description" in tool


class TestListTools:
    def test_list(self) -> None:
        resp = client.get("/v1/mcp/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert isinstance(tools, list)
        assert len(tools) > 0
        names = [t["name"] for t in tools]
        assert "retrieve_memories" in names
        assert "store_memory" in names
        assert "list_namespaces" in names

    def test_each_tool_has_schema(self) -> None:
        resp = client.get("/v1/mcp/tools")
        for tool in resp.json():
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert isinstance(tool["input_schema"], dict)


class TestGetTool:
    def test_get_existing(self) -> None:
        resp = client.get("/v1/mcp/tools/store_memory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "store_memory"
        assert "input_schema" in data
        assert "properties" in data["input_schema"]

    def test_get_nonexistent(self) -> None:
        resp = client.get("/v1/mcp/tools/no_such_tool")
        assert resp.status_code == 404


class TestListResources:
    def test_list(self) -> None:
        resp = client.get("/v1/mcp/resources")
        assert resp.status_code == 200
        resources = resp.json()
        assert isinstance(resources, list)
        assert len(resources) >= 2
        names = [r["name"] for r in resources]
        assert "memory_resource" in names
        assert "graph_neighbors_resource" in names


class TestGetResource:
    def test_get_existing(self) -> None:
        resp = client.get("/v1/mcp/resources/memory_resource")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "memory_resource"
        assert "uri_template" in data
        assert "{memory_id}" in data["uri_template"]

    def test_get_nonexistent(self) -> None:
        resp = client.get("/v1/mcp/resources/no_such_resource")
        assert resp.status_code == 404


class TestListPrompts:
    def test_list(self) -> None:
        resp = client.get("/v1/mcp/prompts")
        assert resp.status_code == 200
        prompts = resp.json()
        assert isinstance(prompts, list)
        assert len(prompts) >= 1
        assert prompts[0]["name"] == "memory_context"
        assert len(prompts[0]["arguments"]) >= 1


class TestGetPrompt:
    def test_get_existing(self) -> None:
        resp = client.get("/v1/mcp/prompts/memory_context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "memory_context"
        args = data["arguments"]
        arg_names = [a["name"] for a in args]
        assert "query" in arg_names

    def test_get_nonexistent(self) -> None:
        resp = client.get("/v1/mcp/prompts/no_such_prompt")
        assert resp.status_code == 404
