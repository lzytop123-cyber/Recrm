const { chromium } = require('playwright');
const path = require('path');

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('file://'+path.resolve(__dirname,'../index.html')+'?view=performance');
  await page.waitForSelector('.performance-shell');
  if(await page.locator('[data-okr-tab]').count()!==4)throw new Error('绩效页签数量不正确');

  await page.click('[data-action="performance-rules"]');
  await page.waitForSelector('#modal[open]');
  await page.click('#modal button[value="cancel"]');

  await page.click('[data-okr-tab="assessment"]');
  await page.locator('[data-performance-assessment="5"]').click();
  await page.click('#submitManagerRating');
  await page.click('#confirmManagerRating');
  await page.waitForSelector('[data-okr-tab="assessment"]');

  await page.click('[data-okr-tab="calibration"]');
  await page.click('[data-action="calibrate"]');
  await page.click('#confirmCalibration');
  for(const i of [0,1]){
    await page.locator(`[data-performance-appeal="${i}"]`).click();
    await page.click('#adjustAppeal');
    await page.click('#confirmAppealResolution');
  }
  await page.click('[data-action="lock-performance"]');
  await page.click('#confirmPerformanceLock');
  await page.waitForSelector('[data-okr-tab="payroll"].active');

  await page.click('[data-action="generate-payroll"]');
  await page.click('#confirmPayrollBatch');
  await page.click('[data-action="review-payroll"]');
  await page.click('#confirmPayrollReview');
  await page.click('[data-action="publish-payroll"]');
  await page.click('#confirmPayrollPublish');
  await page.waitForSelector('button:has-text("工资条已发布")');
  if(await page.getByText('待主管评价',{exact:true}).count())throw new Error('流程完成后仍显示待主管评价');
  if(await page.getByText('待申诉结果',{exact:true}).count())throw new Error('流程完成后仍显示待申诉结果');
  await page.screenshot({path:path.resolve(__dirname,'../output/playwright/performance-complete.png'),fullPage:true});
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('PASS performance workflow: rules -> assessment -> calibration/appeals -> lock -> payroll -> publish');
  await browser.close();
})().catch(async e=>{console.error(e);process.exit(1)});
