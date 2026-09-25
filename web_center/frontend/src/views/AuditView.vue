<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import {
  listAuditEvents,
  type AuditEvent,
} from "../api/audit";

const loading = ref(false);
const events = ref<AuditEvent[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);

const filters = reactive({
  actor_username: "",
  resource_type: "",
  action: "",
  outcome: "" as "" | "success" | "failure",
});

const roleLabels: Record<string, string> = {
  admin: "系统管理员",
  manager: "管理人员",
  reviewer: "审核人员",
  viewer: "只读人员",
};

function formatTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
  });
}

const resourceLabels: Record<string, string> = {
  auth: "登录与账户",
  users: "用户与权限",
  projects: "项目管理",
  "survey-batches": "调查批次",
  "survey-tasks": "调查任务",
  "result-submissions": "调查成果",
  "central-records": "成果库",
};

function operationText(row: AuditEvent) {
  if (row.summary) return row.summary;
  const verb = row.action.split(".").at(-1);
  return {
    create: "新增记录",
    update: "修改记录",
    replace: "更新记录",
    delete: "删除记录",
    login: "用户登录",
    logout: "用户退出",
    change_password: "修改密码",
  }[verb ?? ""] ?? "业务操作";
}

async function refresh() {
  loading.value = true;
  try {
    const result = await listAuditEvents({
      ...filters,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    });
    events.value = result.items;
    total.value = result.total;
  } finally {
    loading.value = false;
  }
}

function search() {
  page.value = 1;
  void refresh();
}

function resetFilters() {
  filters.actor_username = "";
  filters.resource_type = "";
  filters.action = "";
  filters.outcome = "";
  page.value = 1;
  void refresh();
}

function handlePageChange(value: number) {
  page.value = value;
  void refresh();
}

onMounted(refresh);
</script>

<template>
  <div class="module-header">
    <div>
      <h1>审计日志</h1>
      <p>
        自动记录重要业务操作，便于了解谁在什么时间进行了哪些处理，历史记录不可修改。
      </p>
    </div>
  </div>

  <el-card shadow="never" class="business-card audit-filter-card">
    <el-form inline>
      <el-form-item label="操作用户">
        <el-input
          v-model="filters.actor_username"
          clearable
          placeholder="用户名"
          style="width: 150px"
        />
      </el-form-item>
      <el-form-item label="结果">
        <el-select
          v-model="filters.outcome"
          clearable
          style="width: 130px"
        >
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failure" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card shadow="never" class="business-card audit-table-card">
    <el-table v-loading="loading" :data="events">
      <el-table-column label="时间" width="185">
        <template #default="{ row }">
          {{ formatTime(row.occurred_at) }}
        </template>
      </el-table-column>
      <el-table-column label="用户" width="165">
        <template #default="{ row }">
          <div>{{ row.actor_username || "未认证" }}</div>
          <div class="audit-secondary">
            {{ roleLabels[row.actor_role] || row.actor_role || "—" }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作内容" min-width="260">
        <template #default="{ row }">{{ operationText(row) }}</template>
      </el-table-column>
      <el-table-column label="业务模块" width="140">
        <template #default="{ row }">{{ resourceLabels[row.resource_type] || "系统管理" }}</template>
      </el-table-column>
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.outcome === 'success' ? 'success' : 'danger'">
            {{ row.outcome === "success" ? "成功" : "失败" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="client_ip" label="操作设备" width="145">
        <template #default="{ row }">
          {{ row.client_ip || "—" }}
        </template>
      </el-table-column>
    </el-table>

    <div class="audit-pagination">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
      />
    </div>
  </el-card>
</template>
