const {chromium}=require('playwright');
const path=require('path');

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('file://'+path.resolve(__dirname,'../index.html')+'?view=projects');
  await page.waitForSelector('.project-kanban');
  if(await page.locator('[data-project-tab]').count()!==7)throw new Error('项目交付总页签数量不正确');
  if(await page.locator('.project-kanban-column').count()!==5)throw new Error('项目看板状态列不完整');
  await page.selectOption('#projectBoardType','AI定制开发');
  const types=await page.locator('.project-board-card>small').allTextContents();
  if(!types.length||types.some(x=>!x.includes('AI定制开发')))throw new Error('业务类型筛选未生效');
  await page.selectOption('#projectBoardType','全部业务');
  await page.locator('[data-project-board-card="2"]').click();
  await page.click('#viewCompleteProject');
  await page.waitForSelector('.project-detail-shell');
  if(!await page.getByText('← 返回项目看板',{exact:true}).count())throw new Error('项目详情未保留看板返回路径');
  await page.click('[data-project-detail-back]');
  await page.waitForSelector('.project-kanban');
  await page.screenshot({path:path.resolve(__dirname,'../output/playwright/project-total-board.png'),fullPage:true});
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('PASS total project board, filter, drill-down and return');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
