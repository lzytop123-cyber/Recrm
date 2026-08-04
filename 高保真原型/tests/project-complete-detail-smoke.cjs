const {chromium}=require('playwright');
const path=require('path');

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('file://'+path.resolve(__dirname,'../index.html')+'?view=projects');
  await page.waitForSelector('[data-project="0"]');
  await page.click('[data-project="0"]');
  await page.waitForSelector('#viewCompleteProject');
  await page.click('#viewCompleteProject');
  await page.waitForSelector('.project-detail-shell');
  if(await page.locator('[data-project-detail-tab]').count()!==5)throw new Error('完整项目页签数量不正确');
  for(const tab of ['milestones','tasks','risks','acceptance','overview']){
    await page.click(`[data-project-detail-tab="${tab}"]`);
    await page.waitForSelector(`[data-project-detail-tab="${tab}"].active`);
  }
  await page.click('[data-project-update="0"]');
  await page.fill('#projectProgressValue','72');
  await page.click('#confirmProjectProgress');
  await page.waitForSelector('.project-detail-kpi strong');
  if(!await page.getByText('72%',{exact:true}).count())throw new Error('项目进度提交后未刷新');
  await page.screenshot({path:path.resolve(__dirname,'../output/playwright/project-complete-detail.png'),fullPage:true});
  await page.click('[data-project-detail-back]');
  await page.waitForSelector('[data-project="0"]');
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('PASS complete project detail navigation and progress update');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
