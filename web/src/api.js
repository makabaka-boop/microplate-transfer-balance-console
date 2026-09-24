// 与 FastAPI /api/compute 交互；规范化 422/409 错误便于页面定位
export async function compute(payload) {
  const res = await fetch('/api/compute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (res.ok) {
    return { ok: true, data: await res.json() }
  }

  if (res.status === 422) {
    const body = await res.json().catch(() => null)
    const issues = (body?.detail ?? []).map((d) => ({
      // loc 形如 ["body","wells",0,"concentration","denominator"]
      loc: Array.isArray(d.loc) ? d.loc.slice(1) : [],
      msg: String(d.msg ?? '请求不合法'),
    }))
    return {
      ok: false,
      status: 422,
      message: '输入未通过校验（422），请按下列提示修正：',
      issues,
    }
  }

  if (res.status === 409) {
    const body = await res.json().catch(() => null)
    return { ok: false, status: 409, detail: body?.detail ?? null }
  }

  const text = await res.text().catch(() => '')
  return { ok: false, status: res.status, message: `服务异常（${res.status}）${text}` }
}

export function fracText(f) {
  if (f == null) return '空'
  return f.denominator === 1 ? String(f.numerator) : `${f.numerator}/${f.denominator}`
}
