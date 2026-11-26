<script setup>
import brandIcon from './assets/goose-icon-64.png'
import chatIcon from './assets/03-welcome-hero.png'
import docIcon from './assets/06-doc-manager.png'
import graphIcon from './assets/07-knowledge-graph.png'
import historyIcon from './assets/08-session-history.png'
</script>

<template>
  <router-view v-if="$route.path.startsWith('/m')" />
  <el-container v-else class="layout">
    <el-header class="header">
      <img :src="brandIcon" class="header-icon" alt="小鹅助手" />
      <h1 class="title">鹅养殖疫病风险评估交互式问答系统</h1>
      <el-button class="mobile-entry" text @click="$router.push('/m')">手机版</el-button>
    </el-header>
    <el-container>
      <el-aside width="220px" class="aside">
        <el-menu router :default-active="$route.path">
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
          <el-menu-item index="/trace">
            <el-icon class="menu-el-icon"><Connection /></el-icon>
            <span>全链路溯源</span>
          </el-menu-item>
          <el-menu-item index="/weather">
            <el-icon class="menu-el-icon"><Sunny /></el-icon>
            <span>天气预警</span>
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
.header {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 22px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #dde5da;
  color: #17231b;
}
.header-icon { width: 34px; height: 34px; border-radius: 10px; object-fit: cover; background: #f4f7f1; }
.title { font-size: 16px; font-weight: 650; letter-spacing: -0.01em; margin: 0; color: #17231b; }
.header .mobile-entry { color: #23704a; margin-left: auto; font-weight: 500; }
.header .mobile-entry:hover { color: #1a5638; background: #e1f2e6; }
.aside {
  background: #fff;
  border-right: 1px solid #dde5da;
  padding: 14px 10px;
}
.aside .el-menu { border-right: none; background: transparent; }
.aside .el-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 44px;
  margin-bottom: 4px;
  padding: 0 12px !important;
  border-radius: 12px;
  color: #68776d;
  font-size: 13px;
}
.aside .el-menu-item:hover { background: #f4f7f1; color: #17231b; }
.aside .el-menu-item.is-active { background: #e1f2e6; color: #23704a; font-weight: 600; }
.menu-icon { width: 22px; height: 22px; border-radius: 50%; object-fit: cover; background: #fff; }
.menu-el-icon { width: 22px; height: 22px; font-size: 18px; color: #23704a; }
</style>
