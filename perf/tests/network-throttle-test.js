import { chromium } from 'k6/browser';
import { check } from 'k6';

export const options={

    scenarios:{
        browser_test:{
            executor:'shared-iterations',
            options:{
                browser:{
                    type:'chromium'
                }
            }

        }
    }
}
export default async function (){
    const page=browser.newPage()
    page.throttleNetwork(networkProfiles['Slow JG'])
    await page.goto('https://www.google.com/')
    page.close()
}