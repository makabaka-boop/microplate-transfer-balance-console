import type { ReviewRequestBody, ReviewResponse } from "./types";

/** 调用后端 /api/review；409/422 同样解析为结构化 JSON 返回。 */
export async function submitReview(body: ReviewRequestBody): Promise<{
  status: number;
  data: ReviewResponse;
}> {
  const res = await fetch("/api/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await res.json()) as ReviewResponse;
  return { status: res.status, data };
}
