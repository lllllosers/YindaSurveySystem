<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { Refresh, Search } from "@element-plus/icons-vue";

import {
  getMasterDataSnapshot,
  type MasterDataSnapshot,
} from "../api/masterData";

const loading = ref(false);
const snapshot = ref<MasterDataSnapshot | null>(null);
const activeTab = ref("departments");
const keyword = ref("");

const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase());
const includesKeyword = (...values: Array<string | null | undefined>) => {
  const query = normalizedKeyword.value;
  return !query || values.some((value) => value?.toLowerCase().includes(query));
};

const departments = computed(() =>
  (snapshot.value?.departments ?? []).filter((item) =>
    includesKeyword(item.name, item.business_code, item.master_key),
  ),
);
const offices = computed(() =>
  (snapshot.value?.offices ?? []).filter((item) =>
    includesKeyword(item.name, item.parent_name, item.business_code, item.master_key),
  ),
);
const canals = computed(() =>
  (snapshot.value?.canals ?? []).filter((item) =>
    includesKeyword(item.name, item.parent_name, item.canal_level, item.master_key),
  ),
);
const scopes = computed(() =>
  (snapshot.value?.management_scopes ?? []).filter((item) =>
    includesKeyword(
      item.canal_name,
      item.organization_name,
      item.description,
      item.master_key,
    ),
  ),
);

function scopeRange(item: NonNullable<MasterDataSnapshot>["management_scopes"][number]) {
  if (item.range_mode === "whole") return "全段";
  if (item.range_mode === "segment_unknown") return "分段（桩号待定）";
  return `${item.start_stake_text ?? "-"} — ${item.end_stake_text ?? "-"}`;
}

async function loadData() {
  loading.value = true;
  try {
    snapshot.value = await getMasterDataSnapshot();
  } catch {
    ElMessage.error("正式主数据加载失败，请检查后端服务状态");
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
</script>

<template>
  <div class="module-header master-header">
    <div>
      <div class="eyebrow">OFFICIAL MASTER DATA</div>
      <h1>正式主数据</h1>
      <p>Web 与桌面端共同使用的 V1.2 组织、渠系及管理范围只读基线。</p>
    </div>
    <div class="header-actions">
      <el-input
        v-model="keyword"
        :prefix-icon="Search"
        clearable
        placeholder="搜索名称、编码或标识"
        class="master-search"
      />
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
    </div>
  </div>

  <el-skeleton v-if="loading && !snapshot" :rows="8" animated />

  <template v-else-if="snapshot">
    <div class="master-summary-grid">
      <div class="summary-tile blue">
        <span>管理处</span><strong>{{ snapshot.summary.department_count }}</strong>
      </div>
      <div class="summary-tile cyan">
        <span>管理所</span><strong>{{ snapshot.summary.office_count }}</strong>
      </div>
      <div class="summary-tile violet">
        <span>渠道</span><strong>{{ snapshot.summary.canal_count }}</strong>
      </div>
      <div class="summary-tile amber">
        <span>管理范围</span><strong>{{ snapshot.summary.management_scope_count }}</strong>
      </div>
    </div>

    <el-card shadow="never" class="business-card master-card">
      <div class="contract-strip">
        <div>
          <span class="contract-label">主数据版本</span>
          <strong>{{ snapshot.summary.master_data_version }}</strong>
        </div>
        <div>
          <span class="contract-label">管理范围版本</span>
          <strong>{{ snapshot.summary.management_scope_version }}</strong>
        </div>
        <div class="contract-hash">
          <span class="contract-label">契约校验值</span>
          <code>{{ snapshot.summary.contract_sha256.slice(0, 16) }}…</code>
        </div>
        <el-tag type="success" effect="light">只读 · 已校验</el-tag>
      </div>

      <el-tabs v-model="activeTab" class="master-tabs">
        <el-tab-pane :label="`管理处 ${departments.length}`" name="departments">
          <el-table :data="departments" stripe height="520">
            <el-table-column prop="name" label="管理处名称" min-width="180" />
            <el-table-column prop="business_code" label="业务编码" width="140" />
            <el-table-column prop="master_key" label="主数据标识" min-width="220" />
            <el-table-column prop="sort_order" label="顺序" width="80" align="center" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`管理所 ${offices.length}`" name="offices">
          <el-table :data="offices" stripe height="520">
            <el-table-column prop="name" label="管理所名称" min-width="180" />
            <el-table-column prop="parent_name" label="所属管理处" min-width="170" />
            <el-table-column prop="business_code" label="业务编码" width="140" />
            <el-table-column prop="master_key" label="主数据标识" min-width="220" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`渠道 ${canals.length}`" name="canals">
          <el-table :data="canals" stripe height="520">
            <el-table-column prop="name" label="渠道名称" min-width="180" />
            <el-table-column prop="canal_level" label="层级" width="110">
              <template #default="scope">
                <el-tag size="small" effect="plain">{{ scope.row.canal_level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="parent_name" label="上级渠道" min-width="160">
              <template #default="scope">{{ scope.row.parent_name ?? "—" }}</template>
            </el-table-column>
            <el-table-column prop="master_key" label="主数据标识" min-width="220" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`管理范围 ${scopes.length}`" name="scopes">
          <el-table :data="scopes" stripe height="520">
            <el-table-column prop="canal_name" label="渠道" min-width="170" />
            <el-table-column prop="organization_name" label="管理单位" min-width="180" />
            <el-table-column label="管理区间" min-width="190">
              <template #default="scope">{{ scopeRange(scope.row) }}</template>
            </el-table-column>
            <el-table-column prop="description" label="说明" min-width="220">
              <template #default="scope">{{ scope.row.description ?? "—" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default><el-tag size="small" type="success">有效</el-tag></template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </template>
</template>
