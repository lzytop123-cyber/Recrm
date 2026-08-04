const {chromium}=require('playwright');
const path=require('path');

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('file://'+path.resolve(__dirname,'../index.html')+'?view=projects');
  await page.waitForSelector('.project-kanban');
  await page.getByRole('button',{name:'交付模板',exact:true}).click();
  await page.waitForSelector('.template-library-list');
  if(await page.locator('[data-template-library-item]').count()!==3)throw new Error('模板库基础模板数量不正确');
  await page.locator('[data-template-library-item="0"]').click();
  await page.waitForSelector('#copyDeliveryTemplate');
  await page.click('#copyDeliveryTemplate');
  await page.click('#confirmCopyTemplate');
  await page.waitForSelector('.template-library-list');
  if(await page.locator('[data-template-library-item]').count()!==4)throw new Error('复制模板后未加入模板库');
  if(!await page.getByText('草稿',{exact:true}).count())throw new Error('复制模板未标记为草稿');
  await page.click('#modal button[value="cancel"]');

  await page.click('[data-project-tab="portfolio"]');
  await page.waitForSelector('.delivery-templates .template-card');
  await page.locator('.delivery-templates .template-card').first().click();
  await page.waitForSelector('#useDeliveryTemplate');
  if(!await page.getByText('AI产品销售交付',{exact:true}).count())throw new Error('模板卡片未打开对应详情');
  await page.screenshot({path:path.resolve(__dirname,'../output/playwright/delivery-template-detail.png'),fullPage:true});
  await page.click('#useDeliveryTemplate');
  await page.fill('#templateProjectName','海川科技AI产品交付');
  await page.fill('#templateProjectCustomer','海川科技');
  await page.click('#confirmTemplateProject');
  await page.waitForSelector('[data-project-tab="initiation"].active');
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('PASS delivery template library, card detail, copy and use flow');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
