import { expect, test } from "@playwright/test";

/**
 * 唯一的浏览器测试：预置示例（A:100@3, B 空；A→B 25, B→A 20）
 * 真实点击提交，断言页面展示逐步追溯、最终孔位表与守恒证据。
 */
test("一次真实提交：逐步结果、最终表与守恒证据均展示", async ({ page }) => {
  await page.goto("/");

  // 预置数据已在页面中：确认编辑器存在
  await expect(page.getByRole("heading", { name: "孔位（2/48，至少 2）" })).toBeVisible();

  // 真实提交一次
  await page.getByTestId("submit-review").click();

  // 全板守恒证据
  await expect(page.getByText("溶质量守恒：成立", { exact: true })).toBeVisible();
  await expect(page.getByText("总体积守恒：成立", { exact: true })).toBeVisible();
  await expect(page.getByText("初始总溶质").first()).toBeVisible();

  // 逐步追溯：两步都渲染，且显示精确分数（B→A 20μL 移走溶质 60）
  await expect(page.getByRole("heading", { name: /逐步追溯（2 步/ })).toBeVisible();
  const traceRows = page.locator(".trace-row");
  await expect(traceRows).toHaveCount(2);
  await expect(traceRows.nth(1)).toContainText("60");

  // 最终孔位表：A 终态 95 μL、B 5 μL
  await expect(page.getByRole("heading", { name: "最终孔位表" })).toBeVisible();
  await expect(page.locator(".final-cell", { hasText: /^A/ })).toContainText("95 μL");
  await expect(page.locator(".final-cell", { hasText: /^B/ })).toContainText("5 μL");

  // 编辑后旧结论被清除
  await page.getByLabel("第 1 步取液量").fill("30");
  await expect(page.getByText("复核结果将显示在这里")).toBeVisible();
  await expect(page.getByText("溶质量守恒：成立")).toHaveCount(0);
});
