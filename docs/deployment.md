# 部署文档

> 阶段 0 占位，阶段 4 完善（Docker Compose 一键启动）。

## 规划

- 服务编排：`docker/docker-compose.yml`
  - backend：FastAPI
  - mysql：关系型数据库（会话 / 文档元数据）
  - chroma：向量库持久化（挂载卷）
  - redis：缓存
- 镜像构建：`docker/Dockerfile`

## TODO

- [ ] 编写完整 Dockerfile（Python 3.11）
- [ ] 完善 docker-compose（健康检查、持久化挂载、环境变量注入）
- [ ] 补基础日志（请求时间、token 消耗、错误信息）
