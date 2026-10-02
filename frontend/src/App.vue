<script setup>
import shieldIcon from './assets/05-risk-shield.png'
import chatIcon from './assets/03-welcome-hero.png'
import docIcon from './assets/06-doc-manager.png'
import graphIcon from './assets/07-knowledge-graph.png'
import historyIcon from './assets/08-session-history.png'
</script>

<template>
  <el-container class="layout">
    <el-header class="header">
      <img :src="shieldIcon" class="header-icon" alt="" />
      <h1 class="title">鹅养殖疫病风险评估交互式问答系统</h1>
    </el-header>
    <el-container>
      <el-aside width="220px" class="aside">
        <el-menu router default-active="/chat">
          <el-menu-item index="/chat">
            <img :src="chatIcon" class="menu-icon" alt="" />
            <span>对话</span>
          </el-menu-item>
          <el-menu-item index="/upload">
            <img :src="docIcon" class="menu-icon" alt="" />
            <span>文档管理</span>
          </el-menu-item>
          <el-menu-item index="/graph">
            <img :src="graphIcon" class="menu-icon" alt="" />
            <span>知识图谱</span>
          </el-menu-item>
          <el-menu-item index="/history">
            <img :src="historyIcon" class="menu-icon" alt="" />
            <span>会话历史</span>
          </el-menu-item>
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
.header { background: #1f6f54; color: #fff; display: flex; align-items: center; gap: 10px; }
.header-icon { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; background: #fff; }
.title { font-size: 18px; margin: 0; }
.aside { border-right: 1px solid #e4e7ed; }
.aside .el-menu-item { display: flex; align-items: center; gap: 8px; }
.menu-icon { width: 24px; height: 24px; border-radius: 50%; object-fit: cover; background: #fff; }
.main { background: #f5f7fa; }
</style>
