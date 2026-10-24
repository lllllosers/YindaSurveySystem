type ImportError = { code?: string; response?: { status?: number } };

// A failed transport does not tell us whether the server committed. Only GET
// the saved status here; never retry the import POST.
export async function resolveImportError<T extends { status: string }>(
  error: ImportError,
  readSubmission: () => Promise<T>,
) {
  const status = error.response?.status;
  const timedOut = error.code === "ECONNABORTED" || error.code === "ETIMEDOUT";
  const uncertain = status === undefined;
  let message: string;
  if (uncertain) {
    message = timedOut
      ? "请求超时，入库结果尚未确认。请稍后刷新成果状态，勿重复提交。"
      : "网络连接中断，入库结果尚未确认。请恢复网络后刷新成果状态，勿重复提交。";
  } else if (status === 409) {
    message = "当前状态或业务核验存在冲突，请查看最新状态，处理后重新核验并审核。";
  } else if (status === 410) {
    message = "成果原文件已缺失，无法入库，请联系管理员恢复原文件。";
  } else if (status >= 500) {
    message = "服务器处理入库时发生异常，请联系管理员检查日志并确认最新状态。";
  } else if (status === 403) {
    message = "当前账户没有正式入库权限。";
  } else {
    message = "入库请求未完成，请查看最新成果状态。";
  }
  let submission: T | null = null;
  try {
    submission = await readSubmission();
  } catch {
    // Preserve the uncertain result when status retrieval also fails.
  }
  const imported = submission?.status === "imported";
  return {
    submission,
    uncertain: uncertain && !imported,
    imported,
    message: imported ? "已查询确认：成果已正式入库。" : message,
  };
}
