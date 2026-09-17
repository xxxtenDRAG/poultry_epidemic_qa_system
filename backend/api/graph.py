"""知识图谱接口：GET /api/graph/query。

阶段 1：mock 返回；
阶段 3：NetworkX 图谱检索（实体 → 关联实体/关系）。
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class GraphResult(BaseModel):
    entity: str
    edges: list[GraphEdge] = []


@router.get("/graph/query", response_model=GraphResult)
async def query_graph(entity: str = Query(..., description="查询实体")):
    """查询实体及其关联关系。"""
    # TODO(阶段 3)：接入 NetworkX 图谱
    return GraphResult(entity=entity, edges=[])
