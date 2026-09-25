<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Download, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import {
  centralRecordExportUrl,
  getCentralRecord,
  getCentralRecordSummary,
  listCentralRecords,
  type CentralRecord,
  type CentralRecordDetail,
  type CentralRecordSummary,
  type NamedCount,
} from "../api/centralRecords";

const loading = ref(false);
const detailLoading = ref(false);
const rows = ref<CentralRecord[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(30);
const search = ref("");
const formCode = ref("");
const organizationUid = ref("");
const canalUid = ref("");
const summary = ref<CentralRecordSummary | null>(null);
const detail = ref<CentralRecordDetail | null>(null);
const drawerVisible = ref(false);

const filters = computed(() => ({
  search: search.value || undefined,
  form_code: formCode.value || undefined,
  organization_unit_uid: organizationUid.value || undefined,
  canal_unit_uid: canalUid.value || undefined,
}));

const maxOrganizationCount = computed(() =>
  Math.max(1, ...(summary.value?.by_organization.map((item) => item.count) ?? [1])),
);

function formatTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function apiError(error: any, fallback: string) {
  ElMessage.error(error?.response?.data?.detail ?? fallback);
}

async function refreshSummary() {
  try {
    summary.value = await getCentralRecordSummary();
  } catch (error: any) {
    apiError(error, "成果汇总读取失败");
  }
}

async function refresh() {
  loading.value = true;
  try {
    const data = await listCentralRecords({
      ...filters.value,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    });
    rows.value = data.items;
    total.value = data.total;
  } catch (error: any) {
    apiError(error, "中央成果记录读取失败");
  } finally {
    loading.value = false;
  }
}

async function applyFilters() {
  page.value = 1;
  await refresh();
}

function clearFilters() {
  search.value = "";
  formCode.value = "";
  organizationUid.value = "";
  canalUid.value = "";
  void applyFilters();
}

async function openDetail(row: CentralRecord) {
  drawerVisible.value = true;
  detailLoading.value = true;
  detail.value = null;
  try {
    detail.value = await getCentralRecord(row.survey_record_uid);
  } catch (error: any) {
    apiError(error, "记录详情读取失败");
  } finally {
    detailLoading.value = false;
  }
}

function exportCsv() {
  window.open(centralRecordExportUrl(filters.value), "_blank");
}

function barWidth(item: NamedCount) {
  return `${Math.max(5, (item.count / maxOrganizationCount.value) * 100)}%`;
}

function payloadText(key: string) {
  const value = detail.value?.record_payload?.[key];
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join("、") || "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

onMounted(async () => {
  await Promise.all([refresh(), refreshSummary()]);
});
</script>

<template>
  <div class="module-header">
    <div>
      <h1>数据成果库</h1>
      <p>集中查询已经审核入库的调查成果，按工程、单位、渠道和调查表快速筛选汇总。</p>
    </div>
    <el-button :icon="Download" @click="exportCsv">导出当前筛选 CSV</el-button>
  </div>

  <div class="records-metric-grid">
    <div><span>工程对象</span><strong>{{ summary?.asset_count ?? "—" }}</strong></div>
    <div><span>调查记录</span><strong>{{ summary?.record_count ?? "—" }}</strong></div>
    <div><span>分项评价</span><strong>{{ summary?.inspection_count ?? "—" }}</strong></div>
    <div><span>调查影像</span><strong>{{ summary?.media_count ?? "—" }}</strong></div>
  </div>

  <el-card shadow="never" class="business-card records-filter-card">
    <el-form inline @submit.prevent="applyFilters">
      <el-form-item label="关键词">
        <el-input v-model="search" clearable placeholder="工程名称或业务编号" :prefix-icon="Search" />
      </el-form-item>
      <el-form-item label="表单">
        <el-select v-model="formCode" clearable placeholder="全部表单" style="width: 180px">
          <el-option v-for="item in summary?.by_form ?? []" :key="item.key" :label="`${item.name}（${item.count}）`" :value="item.key" />
        </el-select>
      </el-form-item>
      <el-form-item label="管理单位">
        <el-select v-model="organizationUid" filterable clearable placeholder="全部单位" style="width: 220px">
          <el-option v-for="item in summary?.by_organization ?? []" :key="item.key" :label="`${item.name}（${item.count}）`" :value="item.key" />
        </el-select>
      </el-form-item>
      <el-form-item label="渠道">
        <el-select v-model="canalUid" filterable clearable placeholder="全部渠道" style="width: 220px">
          <el-option v-for="item in summary?.by_canal ?? []" :key="item.key" :label="`${item.name}（${item.count}）`" :value="item.key" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="applyFilters">查询</el-button>
        <el-button @click="clearFilters">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <div class="records-layout">
    <el-card shadow="never" class="business-card records-table-card">
      <template #header>
        <div class="card-header"><span>正式调查记录</span><small>共 {{ total }} 条</small></div>
      </template>
      <el-table v-loading="loading" :data="rows" @row-dblclick="openDetail">
        <el-table-column label="工程" min-width="220">
          <template #default="{ row }">
            <div>{{ row.asset_name || "未命名工程" }}</div>
            <div class="result-secondary">{{ row.business_code || row.engineering_asset_uid }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="form_code" label="调查表" width="130" />
        <el-table-column prop="organization_name" label="管理单位" min-width="150" />
        <el-table-column prop="canal_name" label="渠道" min-width="160" />
        <el-table-column label="版本" width="80">
          <template #default="{ row }">V{{ row.revision_no }}</template>
        </el-table-column>
        <el-table-column label="入库时间" width="180">
          <template #default="{ row }">{{ formatTime(row.imported_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && rows.length === 0" description="尚无正式入库的调查记录" />
      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        background
        layout="prev, pager, next, total"
        :total="total"
        class="records-pagination"
        @current-change="refresh"
      />
    </el-card>

    <el-card shadow="never" class="business-card records-distribution-card">
      <template #header><div class="card-header"><span>单位成果分布</span><small>按调查记录</small></div></template>
      <el-empty v-if="(summary?.by_organization.length ?? 0) === 0" description="暂无分布数据" />
      <div v-for="item in summary?.by_organization ?? []" :key="item.key" class="distribution-row">
        <div><span>{{ item.name }}</span><b>{{ item.count }}</b></div>
        <div class="distribution-track"><i :style="{ width: barWidth(item) }"></i></div>
      </div>
    </el-card>
  </div>

  <el-drawer v-model="drawerVisible" title="调查记录详情" size="58%">
    <div v-loading="detailLoading">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工程名称">{{ detail.asset_name || "—" }}</el-descriptions-item>
          <el-descriptions-item label="业务编号">{{ detail.business_code || "—" }}</el-descriptions-item>
          <el-descriptions-item label="管理单位">{{ detail.organization_name }}</el-descriptions-item>
          <el-descriptions-item label="渠道">{{ detail.canal_name }}</el-descriptions-item>
          <el-descriptions-item label="调查来源" :span="2">由桌面端调查任务采集并经中心审核入库</el-descriptions-item>
        </el-descriptions>
        <h3 class="drawer-section-title">调查结论</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="调查日期">{{ payloadText("survey_date") }}</el-descriptions-item>
          <el-descriptions-item label="总体评价">{{ payloadText("overall_grade") }}</el-descriptions-item>
          <el-descriptions-item label="调查人员">{{ payloadText("surveyor_signatures") }}</el-descriptions-item>
          <el-descriptions-item label="记录版本">V{{ detail.revision_no }}</el-descriptions-item>
          <el-descriptions-item label="调查意见" :span="2">{{ payloadText("survey_comment") }}</el-descriptions-item>
        </el-descriptions>
        <h3 class="drawer-section-title">分项评价（{{ detail.inspections.length }}）</h3>
        <el-table :data="detail.inspections" border>
          <el-table-column prop="category" label="类别" min-width="120" />
          <el-table-column prop="item_name" label="检查项目" min-width="150" />
          <el-table-column prop="grade" label="评价" width="100" />
          <el-table-column prop="description" label="说明" min-width="180" />
          <el-table-column prop="remark" label="备注" min-width="140" />
        </el-table>
        <h3 class="drawer-section-title">影像元数据（{{ detail.media.length }}）</h3>
        <el-table :data="detail.media" border>
          <el-table-column prop="original_filename" label="文件名" min-width="180" />
          <el-table-column prop="media_kind" label="类型" width="100" />
          <el-table-column prop="media_role" label="用途" width="100" />
          <el-table-column prop="part_name" label="部位" min-width="130" />
          <el-table-column prop="notes" label="备注" min-width="150" />
        </el-table>
        <el-collapse class="protocol-collapse">
          <el-collapse-item title="查看技术追溯信息" name="raw">
            <div class="tracking-grid">
              <span>记录识别码</span><code>{{ detail.survey_record_uid }}</code>
              <span>来源任务识别码</span><code>{{ detail.source_task_uid || "—" }}</code>
              <span>分管范围识别码</span><code>{{ detail.source_management_scope_uid || "—" }}</code>
              <span>成果提交识别码</span><code>{{ detail.current_submission_uid }}</code>
            </div>
          </el-collapse-item>
        </el-collapse>
      </template>
    </div>
  </el-drawer>
</template>
