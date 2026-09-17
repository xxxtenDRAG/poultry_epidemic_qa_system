"""知识图谱接口：GET /api/graph/query, GET /api/graph/overview（阶段 3 接入 NetworkX 真实检索）。

query：输入实体 → 返回该实体一跳子图（节点 + 关系边），供前端 ECharts 渲染。
overview：图谱统计（节点/边/社区数），可选。
首次调用加载 <项目根>/data/knowledge_graph.json；若文件缺失返回空（不报错）。
"""
from fastapi import APIRouter, Query

from knowledge_graph import retriever

router = APIRouter()


@router.get("/graph/query")
async def query_graph(entity: str = Query(..., description="查询实体")):
    """查询实体及其一跳关联子图。"""
    return retriever.query_entity(entity)


@router.get("/graph/overview")
async def graph_overview():
    """图谱规模与社区统计。"""
    return retriever.get_overview()