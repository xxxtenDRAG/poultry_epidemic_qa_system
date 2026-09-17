<script setup>
// 全局布局：顶部标题 + 左侧历史列表 + 右侧内容区
</script>

<template>
  <el-container class="layout">
    <el-header class="header">
      <h1 class="title">鹅养殖疫病风险评估交互式问答系统</h1>
    </el-header>
    <el-container>
      <el-aside width="220px" class="aside">
        <el-menu router default-active="/chat">
          <el-menu-item index="/chat">对话</el-menu-item>
          <el-menu-item index="/upload">文档管理</el-menu-item>
          <el-menu-item index="/graph">知识图谱</el-menu-item>
          <el-menu-item index="/history">会话历史</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
.layout { height: 100vh; }
.header { background: #1f6f54; color: #fff; display: flex; align-items: center; }
.title { font-size: 18px; margin: 0; }
.aside { border-right: 1px solid #e4e7ed; }
.main { background: #f5f7fa; }
</style>
