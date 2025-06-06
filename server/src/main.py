from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, Union, Dict, Any
from aiarr import AiArr
from pydantic import BaseModel
import json
import logging
from datetime import datetime # Import datetime
import logging.config
import sys
import os
import uvicorn
import asyncio

# This is your original application, now specifically for API routes
api_app = FastAPI(
    title="AiArr API",
    # OpenAPI docs will be available at /api/docs, /api/redoc etc.
)

# Setup Logging
loglevel_str = os.environ.get('LOGLEVEL', default='DEBUG')
loglevel = getattr(logging, loglevel_str, "DEBUG")
LOGGING_CONFIG = { 
    'version': 1,
    'formatters': { 
        'standard': { 
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': { 
        'default': { 
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': loglevel,
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['default'],
            'level': loglevel,
        },
        'main': {  
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'aiarr': {  
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'gemini': { 
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'jellyfin': {  
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'sonarr': {  
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'radarr': {  
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'tmdb': { 
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'database': { 
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'settings': { 
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'migration': { 
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'fastapi': {
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'uvicorn': {
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
        'apscheduler': {
            'handlers': ['default'],
            'level': loglevel,
            'propagate': False
        },
    },
}

# Initialize logging configuration
logging.config.dictConfig(LOGGING_CONFIG)

# Create logger for the main application module
logger = logging.getLogger(__name__)

# --- Create the main root application ---
# This 'app' will be the one Uvicorn runs.
app = FastAPI(title="AiArr")

# Add middleware to log all requests to the root app
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response
    
# Global error handling for the root app
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global error: {exc}", exc_info=True)
    # Consider returning JSONResponse for consistency if preferred:
    # from fastapi.responses import JSONResponse
    # return JSONResponse(status_code=500, content={"detail": str(exc)})
    return {"detail": str(exc)}

# Setup CORS for the api_app
origins = ["*"] # Define origins for CORS
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CustomPromptRequest(BaseModel):
    prompt: str
    media_name: Optional[str] = None
    name: Optional[str] = None # Add name field
    favorites_option: Optional[str] = None

class ScheduleSearchRequest(BaseModel):
    prompt: Optional[str] = None
    year: Union[int|str] = "*"
    month: Union[int|str] = "*" 
    hour: Union[int|str] = "*"
    day: Union[int|str] = "*"
    minute: Union[int|str] = "*"
    day_of_week: Optional[str] = "*"
    enabled: Optional[bool] = True

class RequestMediaBody(BaseModel):
    media_type: str
    quality_profile_id: Optional[int] = None
    save_default: Optional[bool] = False

class SettingUpdateRequest(BaseModel):
    """Request model for updating a setting."""
    value: Optional[str] = None

class SettingResponse(BaseModel):
    """Response model for a setting."""
    name: str
    group: str
    value: Optional[str]
    default: Optional[str]
    type: str
    description: Optional[str]

class ScheduleSearchResponse(BaseModel):
    id: str
    success: bool
    message: str

class JobTriggerResponse(BaseModel):
    success: bool
    message: str

class PromptPreviewRequest(BaseModel):
    limit: int
    media_name: Optional[str] = None
    prompt: Optional[str] = None
    favorite_option: Optional[str]

# Store single instance of AiArr
_ai_arr_instance = None

def get_ai_arr() -> AiArr:
    """
    Dependency injection for the AiArr class.
    Returns the same instance for the entire application lifetime.
    """
    global _ai_arr_instance
    if _ai_arr_instance is None:
        _ai_arr_instance = AiArr()
        logger.info("Initialized AiArr instance")
    return _ai_arr_instance

@app.on_event("startup")
async def startup_event():
    """
    Tasks to run when the application starts.
    This includes initializing AiArr and starting the scheduler.
    """
    logger.info("Application startup: Initializing AiArr and starting scheduler...")
    logger.info(f"Log level set to: {loglevel}")
    current_loop_id_at_startup = id(asyncio.get_event_loop())
    logger.info(f"FastAPI startup_event running in event loop ID: {current_loop_id_at_startup}")
    ai_arr_instance = get_ai_arr() # Ensures AiArr and its scheduler are initialized
    if ai_arr_instance and hasattr(ai_arr_instance, 'scheduler') and \
       hasattr(ai_arr_instance.scheduler, 'scheduler') and \
       not ai_arr_instance.scheduler.scheduler.running:
        try:
            # Start the underlying APScheduler
            ai_arr_instance.scheduler.scheduler.start()
            logger.info("APScheduler (AsyncIOScheduler) started successfully.")
            # Now load the schedules from the database into the started scheduler
            ai_arr_instance.scheduler.load_schedules()
            logger.info("Schedules loaded into APScheduler.")
        except Exception as e:
            logger.error(f"Failed to start APScheduler: {e}", exc_info=True)

@api_app.get("/users")
async def get_jellyfin_users(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve all users from Jellyfin.
    """
    users = ai_arr.get_users()
    if users is None:
        # This could happen if Jellyfin is not configured or if there's an API error
        raise HTTPException(status_code=503, detail="Jellyfin service unavailable or error fetching users.")
    return users

# --- Plex Endpoints ---
@api_app.get("/plex/users")
async def get_plex_users(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve all managed users from Plex.
    """
    users = ai_arr.plex_get_users()
    if users is None:
        # This could happen if Plex is not configured or if there's an API error
        raise HTTPException(status_code=503, detail="Plex service unavailable or error fetching users.")
    return users

@api_app.get("/plex/recently_watched")
async def plex_recently_watched(
    limit: Optional[int] = None,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve recently watched items from the Plex API for the default user.
    """
    return ai_arr.plex_get_recently_watched(limit)

@api_app.get("/plex/recently_watched_filtered")
async def plex_recently_watched_filtered(
    limit: Optional[int] = None,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve filtered recently watched items from the Plex API for the default user.
    """
    items = ai_arr.plex_get_recently_watched_filtered(limit)
    if items is None:
         # This could happen if Plex is not configured or if there's an API error
        raise HTTPException(status_code=503, detail="Plex service unavailable or error fetching recently watched items.")
    # The filtered items are already PlexMediaItem dataclasses, which FastAPI can serialize
    # If you specifically need *only* the names, you would call get_items_filtered with attribute_filter="name"
    # but the Jellyfin endpoint returns the full filtered objects, so we'll match that.
    return items

@api_app.get("/plex/all")
async def plex_all(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve all movie and TV show items from the Plex library, filtered.
    """
    items = ai_arr.plex_get_all_items_filtered()
    if items is None:
         # This could happen if Plex is not configured or if there's an API error
        raise HTTPException(status_code=503, detail="Plex service unavailable or error fetching all items.")
    return items # Returns List[PlexMediaItem] or List[str]

@api_app.get("/sync_watch_history")
async def sync_watch_history(
    limit: Optional[int] = None,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve recently watched items from the Jellyfin API.
    """
    return ai_arr.sync_watch_history()

@api_app.get("/jellyfin/recently_watched")
async def jellyfin_recently_watched(
    limit: Optional[int] = None,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve recently watched items from the Jellyfin API.
    """
    return ai_arr.jellyfin_get_recently_watched(limit)

@api_app.get("/jellyfin/recently_watched_filtered")
async def jellyfin_recently_watched_filtered(
    limit: Optional[int] = None,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve recently watched items from the Jellyfin API.
    """
    return ai_arr.jellyfin_get_recently_watched_filtered(limit)

@api_app.get("/jellyfin/all")
async def jellyfin_all(
    limit: Optional[int] = None,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve all items from the Jellyfin API.
    """
    # The Jellyfin endpoint returns a string, which is inconsistent with the filtered methods.
    # Let's make the Plex endpoint return the filtered objects for consistency with other filtered methods.
    # If a string is truly needed, a separate endpoint or parameter could be added.
    # For now, mirroring the *filtered* output structure.
    items = ai_arr.jellyfin.get_all_items_filtered() # This returns List[ItemsFiltered] or List[str]
    if items is None:
         # This could happen if Jellyfin is not configured or if there's an API error
        raise HTTPException(status_code=503, detail="Jellyfin service unavailable or error fetching all items.")
    # If the original Jellyfin endpoint truly returned a string, this would need adjustment.
    # Assuming the goal is the filtered list of objects/names.
    # The original endpoint name `jellyfin_get_all_videos_to_string` suggests it returned a string.
    return items # Returning the list of objects/names as per get_items_filtered output

###
# Gemini
###

@api_app.get("/gemini/similar_media/search/{search_id}")
async def gemini_similar_media_by_search(
    search_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Run a saved search by ID.
    """
    logger.info(f"Running saved search with ID: {search_id}")
    try:
        search = ai_arr.db.get_search(search_id)
        if not search:
            raise HTTPException(status_code=404, detail="Search not found")
        return await ai_arr.get_similar_media(media_name=None, custom_prompt=search["prompt"], search_id=search_id)
    except Exception as e:
        logger.error(f"Error running saved search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/gemini/models")
async def get_gemini_models(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve available Gemini models.
    """
    logger.info("Received request to list Gemini models.")
    models = await ai_arr.gemini_get_models() # Await the async call
    if models is None:
        # This could happen if Gemini is not configured or if there's an API error during listing
        raise HTTPException(status_code=503, detail="Gemini service unavailable or error fetching models.")
    return models

@api_app.get("/gemini/similar_media/{media_name}")
async def gemini_similar_media(
    media_name: str,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to find media similar to the given media name using the Gemini API.
    Used for the default recently watched search.
    """
    return await ai_arr.get_similar_media(media_name)

@api_app.post("/gemini/similar_media_custom")
async def gemini_similar_media_with_prompt(
    request: CustomPromptRequest,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to find media similar to the given media name using the Gemini API with a custom prompt.
    Used for the search box in the UI.
    
    Args:
        request: Request body containing the prompt
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Received custom prompt request: {request.prompt}")
    try:
        result = await ai_arr.get_similar_media(media_name=request.media_name, custom_prompt=request.prompt)
        logger.info(f"Successfully processed custom prompt")
        return result
    except Exception as e:
        logger.error(f"Error processing custom prompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

###
# Ollama
###
@api_app.get("/ollama/models")
async def get_ollama_models(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to retrieve available Ollama models.
    """
    logger.info("Received request to list Ollama models.")
    models = await ai_arr.ollama_get_models() 
    if models is None:
        raise HTTPException(status_code=503, detail="Ollama service unavailable or error fetching models.")
    return models

@api_app.post("/request/{tmdb_id}")
async def request_media(
    tmdb_id: str,
    request_body: RequestMediaBody,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Endpoint to request a specific media item using the TMDB ID.
    
    Args:
        tmdb_id: The TMDB ID of the media item
        request_body: Request body containing media_type, quality_profile_id, and save_default
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Requesting media: {tmdb_id} with body: {request_body.model_dump_json(indent=2)}")
    try:
        # Assuming ai_arr.request_media now returns an APIResponse object
        api_response = ai_arr.request_media(
            tmdb_id, request_body.media_type, request_body.quality_profile_id, request_body.save_default
        )

        if api_response.success:
            logger.info(f"Successfully processed media request for {tmdb_id}. Response data: {json.dumps(api_response.data, indent=2) if api_response.data else 'No data'}")
            # On success, the actual data from Sonarr/Radarr is in api_response.data
            return api_response.data 
        else:
            # Handle failure based on the APIResponse
            error_message = api_response.message or "Unknown error during media request."
            details = api_response.error # This is a Dict[str, Any]
            full_error_detail = error_message
            status_code = api_response.status_code if isinstance(api_response.status_code, int) else 500
            logger.error(f"Error requesting media {tmdb_id}: Status {status_code}, Detail: {details}")
            raise HTTPException(status_code=status_code, detail=details)

    except Exception as e:
        # Catch any other unexpected exceptions during the endpoint logic itself
        logger.error(f"Unexpected error in request_media endpoint for {tmdb_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_app.get("/test")
async def test():
    """
    Endpoint to find media similar to the given media name using the Gemini API.
    """
    with open("test.json", 'r') as file:
        data = json.load(file)
        return data
    return data

@api_app.get("/process")
async def process(ai_arr: AiArr = Depends()):
    """
    Main endpoint to process media requests and find similar media.
    """
    return await ai_arr.process_watch_history()

@api_app.get("/media/active")
async def get_active_media(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get all non-ignored media entries from the database.
    """
    return ai_arr.get_active_media()

@api_app.get("/media/ignored")
async def get_ignored_media(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get all ignored media entries from the database.
    """
    return ai_arr.get_ignored_media()
@api_app.post("/media/{media_id}/toggle-ignore")
async def toggle_ignore_status(
    media_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Toggle the ignore status for a specific media entry.
    """
    return ai_arr.toggle_ignore_status(media_id)

@api_app.put("/media/{media_id}/ignore")
async def update_ignore_status(
    media_id: int,
    ignore: bool,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Update the ignore status for a specific media entry.
    """
    return ai_arr.update_ignore_status(media_id, ignore)

@api_app.delete("/media/{media_id}")
async def delete_media_item(
    media_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Delete a specific media entry from the database.
    
    Args:
        media_id: The ID of the media item to delete.
        ai_arr: AiArr instance from dependency injection.
    """
    logger.info(f"Attempting to delete media item with ID: {media_id}")
    try:
        if ai_arr.db.delete_media(media_id):
            return {"status": "success", "message": f"Media item {media_id} deleted successfully."}
        raise HTTPException(status_code=404, detail=f"Media item with ID {media_id} not found.")
    except Exception as e:
        logger.error(f"Error deleting media item {media_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/quality-profiles/{media_type}")
async def get_quality_profiles(
    media_type: str,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get quality profiles for a specific media type.
    
    Args:
        media_type (str): Type of media ('tv' or 'movie')
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Getting quality profiles for {media_type}")
    profiles = ai_arr.get_quality_profiles(media_type)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No quality profiles found for {media_type}")
    return profiles



@api_app.get("/search/stat")
async def get_all_search_stats(
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get token usage statistics for all searches.
    
    Args:
        ai_arr: AiArr instance from dependency injection
    """
    logger.info("Getting all search stats")
    try:
        return ai_arr.db.get_search_stats()
    except Exception as e:
        logger.error(f"Error getting all search stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/search/stat/summary")
async def get_search_stat_summary(
    start_date: Optional[datetime] = None, # Add start_date parameter
    end_date: Optional[datetime] = None,   # Add end_date parameter
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get token usage statistics summary, optionally filtered by a date range.
    
    Args:
        start_date: Optional start date for filtering stats.
        end_date: Optional end date for filtering stats.
        ai_arr: AiArr instance from dependency injection.
    """
    logger.info(f"Getting search stat summary for range: {start_date} to {end_date}")
    try:
        return ai_arr.get_search_stat_summary(start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"Error getting search stat summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/watch-history/grouped")
async def get_watch_history_grouped_endpoint(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get watch history grouped by user, optionally filtered by a date range.
    
    Args:
        start_date: Optional start date for filtering watch history.
        end_date: Optional end date for filtering watch history.
        ai_arr: AiArr instance from dependency injection.
    """
    logger.info(f"Getting grouped watch history for range: {start_date} to {end_date}")
    try:
        return ai_arr.get_watch_history_grouped(start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"Error getting grouped watch history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/media/field/{col_name}")
async def get_media_field_values(
    col_name: str,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get unique values from a specific column in the media table.
    If the column contains comma-delimited strings, they will be split.

    Args:
        col_name (str): The name of the column to query for unique values
                        (e.g., 'media_type', 'title', 'networks', 'genres').
        ai_arr: AiArr instance from dependency injection.
    """
    logger.info(f"Getting unique media values for column: {col_name}")
    try:
        unique_values = ai_arr.get_media_by_field(col_name)
        # The method already returns an empty list on error or if no data,
        # which is fine for a 200 OK response.
        return unique_values
    except Exception as e:
        logger.error(f"Error getting unique media values for column '{col_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while fetching unique values for column '{col_name}'.")

@api_app.get("/search")
async def get_searches(
    limit: int = 10,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get recent searches from the database.
    
    Args:
        limit: Maximum number of searches to return
        ai_arr: AiArr instance from dependency injection
    """
    return ai_arr.get_searches(limit)

@api_app.get("/search/{search_id}")
async def get_search(
    search_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get a specific search by ID.
    
    Args:
        search_id: ID of the search to retrieve
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Getting search with ID: {search_id}")
    try:
        search = ai_arr.db.get_search(search_id)
        if not search:
            raise HTTPException(status_code=404, detail="Search not found")
        return search
    except Exception as e:
        logger.error(f"Error getting search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/search/prompt/preview")
async def preview_search_prompt(
    request: PromptPreviewRequest,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Previews a rendered search prompt based on the provided template, limit, and media name.
    """
    logger.info(f"Generating prompt preview with data: {request.model_dump_json(indent=2)}")
    try:
        # The get_prompt method in AiArr handles the case where request.prompt (template_string) is None
        # by attempting to use self.default_prompt.
        # It also has its own try-except that returns an error message string if rendering fails.
        rendered_prompt = ai_arr.get_prompt(
            limit=request.limit,
            media_name=request.media_name,
            template_string=request.prompt,
            favorite_option=request.favorite_option
        )
        # If get_prompt returns an error message string (e.g., "Error rendering prompt: ..."),
        # we pass it through in the response.
        return { "result": rendered_prompt }
    except Exception as e:
        # This outer try-except catches unexpected errors in this endpoint logic itself,
        # or if get_prompt were to raise an exception instead of returning an error string.
        logger.error(f"Error generating prompt preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while generating prompt preview: {str(e)}")

@api_app.post("/search")
async def save_search(
    request: CustomPromptRequest,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Save a search prompt to the database.
    
    Args:
        request: Request body containing the prompt
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Saving search prompt: {request.prompt}")
    try:
        search = ai_arr.save_search(prompt=request.prompt, name=request.name, favorites_option=request.favorites_option)
        logger.info(f"Saved search with ID: {search}")
        if not search:
            raise HTTPException(status_code=500, detail="Failed to save search")
        return search
    except Exception as e:
        logger.error(f"Error saving search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.put("/search/{search_id}")
async def update_search(
    search_id: int,
    request: CustomPromptRequest,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Update an existing search prompt in the database.
    
    Args:
        search_id: ID of the search to update
        request: Request body containing the updated prompt
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Updating search {search_id} with prompt: {request.prompt}")
    try:
        success = ai_arr.update_search(search_id, request.prompt, request.name, favorites_option=request.favorites_option)
        if not success:
            raise HTTPException(status_code=404, detail="Search not found")
        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.delete("/search/{search_id}")
async def delete_search(
    search_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Delete a search and its associated media entries from the database.
    
    Args:
        search_id: ID of the search to delete
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Deleting search with ID: {search_id}")
    try:
        if ai_arr.delete_search(search_id):
            return {"success": True}
        raise HTTPException(status_code=404, detail="Search not found")
    except Exception as e:
        logger.error(f"Error deleting search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/search/{search_id}/stat")
async def get_search_stats(
    search_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get token usage statistics for a specific search.
    
    Args:
        search_id: ID of the search
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Getting stats for search ID: {search_id}")
    try:
        stats = ai_arr.db.get_search_stats(search_id)
        if not stats:
            return []
        return stats
    except Exception as e:
        logger.error(f"Error getting search stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/schedule/search/{search_id}")
async def get_search_schedule(
    search_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Get the schedule for a specific search.
    
    Args:
        search_id: ID of the search
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Getting schedule for search ID: {search_id}")
    try:
        schedule = ai_arr.db.get_schedule_by_search_id(search_id)
        if not schedule:
            return None
        return schedule
    except Exception as e:
        logger.error(f"Error getting schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.put("/schedule/search/{search_id}")
async def update_search_schedule(
    search_id: int,
    request: ScheduleSearchRequest,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Update or create a schedule for a search.
    
    Args:
        search_id: ID of the search
        request: Request body containing schedule parameters
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Updating schedule for search ID: {search_id}")
    try:
        schedule_data = {
            "year": request.year,
            "month": request.month,
            "hour": request.hour,
            "minute": request.minute,
            "day": request.day,
            "day_of_week": request.day_of_week,
            "enabled": request.enabled,
            "kwargs": json.dumps({
                "media_name": None,
                "search_id": search_id,
                "custom_prompt": request.prompt
            })
        }
        
        schedule = ai_arr.db.get_schedule_by_search_id(search_id)
        schedule_id = None
        if schedule:
            schedule_id = ai_arr.db.update_schedule(search_id=search_id, update_data=schedule_data)
        else:
            func_name = "get_similar_media"
            job_id = f"{func_name}_{search_id}"
            schedule_id = ai_arr.db.add_schedule(
                search_id=search_id,
                job_id=job_id,
                func_name=func_name,
                **schedule_data,
            )
        if not schedule_id:
            raise HTTPException(status_code=500, detail="Failed to update schedule")
            
        # Reload schedules to pick up the updated schedule
        ai_arr.scheduler.load_schedules()
            
        return {"success": True, "schedule_id": schedule_id}
    except Exception as e:
        logger.error(f"Error updating schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.delete("/schedule/search/{search_id}")
async def delete_search_schedule(
    search_id: int,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Delete the schedule for a search.
    
    Args:
        search_id: ID of the search
        ai_arr: AiArr instance from dependency injection
    """
    logger.info(f"Deleting schedule for search ID: {search_id}")
    try:
        if ai_arr.db.delete_schedule_by_search_id(search_id=search_id):
            # Reload schedules to remove the deleted schedule
            ai_arr.scheduler.load_schedules()
            return {"success": True}
        return {"success": False}
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/schedule/job/{job_id}/trigger", response_model=JobTriggerResponse)
async def trigger_job_endpoint(
    job_id: str,
    ai_arr: AiArr = Depends(get_ai_arr),
):
    """
    Manually trigger a scheduled job to run immediately.
    """
    logger.info(f"Received request to trigger job: {job_id}")
    try:
        result = ai_arr.trigger_scheduled_job(job_id)
        if not result["success"]:
            # Determine appropriate status code based on message
            if "not found" in result["message"].lower():
                raise HTTPException(status_code=404, detail=result["message"])
            else:
                # For other failures, trigger_job_now in scheduler logs details
                raise HTTPException(status_code=500, detail=result["message"])
        return result
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error while trying to trigger job '{job_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while triggering job '{job_id}'.")



# Settings management endpoints
@api_app.get("/settings")
async def get_all_settings(
    ai_arr: AiArr = Depends(get_ai_arr),
) -> Dict[str, Dict[str, Any]]:
    """
    Get all settings grouped by their groups.
    """
    return ai_arr.settings.get_all()

@api_app.get("/settings/{group}")
async def get_settings_by_group(
    group: str,
    ai_arr: AiArr = Depends(get_ai_arr),
) -> Dict[str, Any]:
    """
    Get all settings in a group.
    """
    settings = ai_arr.settings.get_settings_by_group(group)
    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings group {group} not found")
    return settings

@api_app.put("/settings/{group}/{name}")
async def update_setting(
    group: str,
    name: str,
    request: SettingUpdateRequest,
    ai_arr: AiArr = Depends(get_ai_arr),
) -> Dict[str, str]:
    """
    Update a setting value.
    """
    success = ai_arr.settings.set(group, name, request.value)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to update setting {group}.{name}")
    return {"status": "success", "message": f"Setting {group}.{name} updated successfully"}

@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on application shutdown.
    """
    global _ai_arr_instance
    if _ai_arr_instance:
        if hasattr(_ai_arr_instance, 'scheduler') and \
           hasattr(_ai_arr_instance.scheduler, 'scheduler') and \
           _ai_arr_instance.scheduler.scheduler.running:
            logger.info("Shutting down APScheduler (AsyncIOScheduler)...")
            # The shutdown method in your Schedule class handles scheduler.shutdown(wait=False)
            _ai_arr_instance.scheduler.shutdown() 
        _ai_arr_instance = None
        logger.info("Cleaned up AiArr instance")

# Mount the API application under the /api path prefix
app.mount("/api", api_app)

# Mount static files for the frontend (Vue.js app)
# This assumes your Dockerfile copies the client's 'dist' output to 'server/static'
# and main.py is in 'server/src/'
static_files_dir = Path(__file__).parent.parent / "static"
#static_files_dir = "/app/client/public"
app.mount("/", StaticFiles(directory=static_files_dir, html=True), name="static_root")
