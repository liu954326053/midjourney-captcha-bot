async def hook(api_host: str, api_secret: str):
    from loguru import logger
    from aiohttp import ClientSession
    session = ClientSession()
    session.headers.update({
        'mj-api-secret': api_secret
    })
    api_host = api_host.rstrip('/')
    logger.info(f'get disabled accounts from {api_host}')
    response = await session.post(f'{api_host}/mj/account/query', json={
        "pageNumber": 0,
        "pageSize": 10000,
        "enable": False,
    })
    accounts = (await response.json())['content']
    logger.info(f'count: {len(accounts)}')

    for account in accounts:
        account_id = account['id']
        disable_reason = account['properties']['disabledReason']
        if '/captcha/' not in disable_reason:
            logger.info(f'skip account: {account_id}, reason: {disable_reason}')
            continue

        logger.info(f'handle account: {account_id}')
        guild_id = account['guildId']
        channel_id = account['channelId']
        user_token = account['userToken']

        from utils import MidjourneyCaptchaBot
        bot = MidjourneyCaptchaBot(logger, user_token, int(guild_id), int(channel_id))
        solved = await bot.imagine('a cat --relax')
        if not solved:
            logger.error(f'failed to imagine for {account_id}')
            continue

        logger.info(f'enable account: {account_id}')
        response = await session.put(f'{api_host}/mj/account/{account_id}/update-reconnect', json={
            "enable": True,
            "channelId": channel_id,
            "guildId": guild_id,
            "userToken": user_token
        })
        logger.info(f'result: {await response.json()}')

    await session.close()


async def run(api_host: str, api_secret: str, cron: str):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler()
    cron_trigger = CronTrigger.from_crontab(cron)
    scheduler.add_job(
        hook(api_host, api_secret),
        trigger=cron_trigger,
        id='hook',
        replace_existing=True,
        max_instances=1
    )
    scheduler.start()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass


async def main():
    import argparse

    parser = argparse.ArgumentParser(description='Midjourney Captcha Bot')
    parser.add_argument('--api_host', type=str, required=True, help='API host')
    parser.add_argument('--api_secret', type=str, required=True, help='API secret')
    parser.add_argument('--cron', type=str, default='* * * * *', help='Cron expression')
    args = parser.parse_args()

    await run(args.api_host, args.api_secret, args.cron)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
