import { test, expect } from '@playwright/test'

// 浏览器层只覆盖一次真实提交与展示；数值正确性由后端 pytest（手算 + 守恒）保证。
test('编辑的孔板与步骤经一次真实提交后，逐步展示与守恒结论正确', async ({ page }) => {
  await page.goto('/')

  // 页面自带示例：母液 S=10μL@1，W1..W5 各预置 1μL 稀释液，5 步各 1μL 逐级转移
  await expect(page.getByRole('heading', { name: /微孔板逐孔转移复核台/ })).toBeVisible()
  await expect(page.locator('.well-card')).toHaveCount(6)
  await expect(page.locator('.transfer-table tbody tr')).toHaveCount(5)

  // 唯一一次真实提交
  await page.getByTestId('compute-submit').click()

  // 守恒横幅：初始/终态总溶质 10、差值 0；初始总体积 15（10 + 5×1），转移只搬运不增减
  const banner = page.getByTestId('conservation-banner')
  await expect(banner).toBeVisible()
  await expect(banner.getByRole('heading', { name: '✅ 守恒核对通过' })).toBeVisible()
  await expect(banner).toContainText('15 → 15 μL')

  // 终态孔板 6 格：S=9μL@1，W1..W4=1μL@1/2..1/16，末端 W5=2μL@1/32
  const cells = page.getByTestId('result-grid').locator('.well-cell')
  await expect(cells).toHaveCount(6)
  const expected = [
    { id: 'S', v: '9 μL', c: '1' },
    { id: 'W1', v: '1 μL', c: '1/2' },
    { id: 'W2', v: '1 μL', c: '1/4' },
    { id: 'W3', v: '1 μL', c: '1/8' },
    { id: 'W4', v: '1 μL', c: '1/16' },
    { id: 'W5', v: '2 μL', c: '1/32' },
  ]
  for (let i = 0; i < expected.length; i++) {
    const e = expected[i]
    const cell = cells.nth(i)
    await expect(cell.locator('.well-cell-id')).toHaveText(e.id)
    await expect(cell.locator('.well-cell-v')).toHaveText(e.v)
    await expect(cell.locator('.well-cell-c')).toHaveText(e.c)
  }

  // 逐步追溯表：5 步，抽查第 1 步与第 5 步前后的来源/目标体积
  const rows = page.getByTestId('trace-table').locator('tbody tr')
  await expect(rows).toHaveCount(5)
  const row1 = rows.nth(0)
  await expect(row1).toContainText('S → W1')
  await expect(row1).toContainText('10 μL') // 步骤 1 前来源 S
  await expect(row1).toContainText('9 μL') // 步骤 1 后来源 S
  await expect(row1).toContainText('2 μL') // 步骤 1 后目标 W1（预置 1 + 移入 1）
  const row5 = rows.nth(4)
  await expect(row5).toContainText('W4 → W5')
  await expect(row5).toContainText('1 μL') // 步骤 5 后 W4 移出 1μL 剩 1μL
  // 第 5 步后目标 W5 浓度为 1/32——中途从已稀释孔取液也被正确传播
  await expect(row5).toContainText('1/32')

  // 每步守恒证据展开：5 行，全板总溶质恒为 10、Δ 之和恒为 0
  await page.getByText(/每步守恒证据/).click()
  const evidenceRows = page.locator('.evidence-table tbody tr')
  await expect(evidenceRows).toHaveCount(5)
  await expect(page.locator('.evidence-table tbody')).toContainText('10')

  // 编辑应清除旧结论：改首个孔位的体积后，结果区消失
  const firstVolume = page.locator('.well-card').first().locator('input[type="number"]').first()
  await firstVolume.fill('11')
  await expect(page.getByTestId('result-view')).not.toBeVisible()
  await expect(page.getByTestId('compute-submit')).toBeVisible()
})
