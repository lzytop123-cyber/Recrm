const { chromium }=require('playwright');
const path=require('path');

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  const url='file://'+path.resolve(__dirname,'../index.html');
  await page.goto(url+'?view=tickets');
  await page.waitForSelector('#ticketDepartmentFilter');
  const labels=await page.locator('#ticketDepartmentFilter option').allTextContents();
  const expected=['全部部门','经营管理层','市场销售中心','新媒体中心','技术交付中心','讲师部','综合管理部','财务部'];
  if(JSON.stringify(labels)!==JSON.stringify(expected))throw new Error('工单部门未完整读取组织架构：'+labels.join(','));
  await page.selectOption('#ticketDepartmentFilter','新媒体中心');
  const receiving=await page.locator('.ticket-card .ticket-tags .status.info').allTextContents();
  if(!receiving.length||receiving.some(x=>x!=='新媒体中心'))throw new Error('部门筛选未生效');
  await page.evaluate(()=>{orgDepartments.push({name:'客户成功部',count:2,head:'待维护',scope:'续约与客户成功',roles:'客户成功经理'});render('tickets')});
  if(!await page.locator('#ticketDepartmentFilter option',{hasText:'客户成功部'}).count())throw new Error('组织架构调整后工单筛选未同步');
  await page.screenshot({path:path.resolve(__dirname,'../output/playwright/ticket-departments-from-organization.png'),fullPage:true});

  await page.goto(url+'?view=performance');
  await page.waitForSelector('.goal-row');
  const boxes=await page.locator('.goal-row').evaluateAll(rows=>rows.map(row=>{const badge=row.querySelector('.goal-copy>span:first-child').getBoundingClientRect(),copy=row.querySelector('.goal-copy>span:last-child').getBoundingClientRect();return{badgeRight:badge.right,copyLeft:copy.left,copyWidth:copy.width}}));
  if(boxes.some(x=>x.copyLeft<x.badgeRight||x.copyWidth<180))throw new Error('目标地图层级标签与文字仍存在重叠');
  await page.screenshot({path:path.resolve(__dirname,'../output/playwright/performance-goal-layout-fixed.png'),fullPage:true});
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('PASS organization departments sync and performance goal layout');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
