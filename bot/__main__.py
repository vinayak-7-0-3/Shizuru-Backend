import asyncio

import uvicorn
import copy

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.config import LOGGING_CONFIG
    

from config import Config
from .tgclient import botmanager
from .database.connection import mongo
from .logger import LOGGER
from .metadata.handler import meta_manager
from .server.routes import router


web_server = FastAPI(title="Shizuru Backend API")
web_server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
web_server.include_router(router)


async def run_fastapi():

    log_config = copy.deepcopy(LOGGING_CONFIG)
    if "filters" not in log_config:
        log_config["filters"] = {}

    log_config["filters"]["webdav_filter"] = {
        "()": "bot.logger.EndpointFilter",
    }

    if "filters" not in log_config["loggers"]["uvicorn.access"]:
        log_config["loggers"]["uvicorn.access"]["filters"] = []

    log_config["loggers"]["uvicorn.access"]["filters"].append("webdav_filter")

    config = uvicorn.Config(
        app=web_server, 
        host="0.0.0.0", 
        port=Config.PORT, 
        log_level="info", 
        log_config=log_config
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    try:
        await botmanager.add_main_bot(Config.TG_BOT_TOKEN)
        if Config.MULTI_CLIENTS:
            for token in Config.MULTI_CLIENTS:
                await botmanager.add_worker_bot(token)
        
        await botmanager.start_all()
        
        await mongo.connect()
        await meta_manager.setup()

        await run_fastapi()

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Exception as e:
        LOGGER.error(f"Startup failed: {e}")
        
    finally:
        LOGGER.info("Stopping services...")
        try:
            await meta_manager.stop()
        except Exception:
            pass
            
        try:
            await mongo.disconnect()
        except Exception:
            pass
            
        try:
            await botmanager.stop_all()
        except Exception:
            pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass