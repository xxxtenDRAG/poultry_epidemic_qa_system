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


@router.get("/graph/entity")
async def entity_detail(entity: str = Query(..., description="实体名称")):
    """单个实体的完整详情：属性 + 关联关系列表。"""
    return retriever.get_entity_detail(entity)


@router.get("/graph/search")
async def search_graph(
    keyword: str = Query(..., description="实体名关键词"),
    limit: int = Query(10, ge=1, le=50, description="返回条数上限"),
):
    """实体模糊搜索（供搜索框联想）：前缀命中优先，其次子串命中。"""
    return retriever.search_entities(keyword, limit=limit)


@router.get("/graph/full")
async def full_graph(type: str = Query("", description="实体类型筛选，留空返回全图")):
    """全图浏览；按类型筛选时返回该类型节点及其一跳邻居。"""
    return retriever.get_full_graph(type.strip() or None)