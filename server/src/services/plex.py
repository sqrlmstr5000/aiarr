import requests
import json
import logging
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timezone
from .models import ItemsFiltered

# Import plexapi
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest, Unauthorized 
from plexapi.utils import toJson
from plexapi.media import Media # For type hinting if needed
from plexapi.video import Movie, Show, Episode, MovieHistory, EpisodeHistory
from plexapi.server import SystemAccount


# Helper function to convert datetime object to ISO 8601 string
def _datetime_to_iso(dt: Optional[datetime]) -> Optional[str]:

    if dt is None:
        return None
    # Ensure datetime is timezone-aware (UTC) before formatting
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

class Plex:
    """
    A class to interact with the Plex API for user and media data using the plexapi library.
    """

    def __init__(self, plex_url: str, plex_token: str, limit: int = 10):
        """
        Initializes the Plex class with API configurations.

        Args:
            plex_url (str): The base URL of the Plex server (e.g., http://localhost:32400).
            plex_token (str): The X-Plex-Token for authentication.
            limit (int): Default limit for API requests.
        """
        self.logger = logging.getLogger(__name__)
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.limit = limit
        self.server: Optional[PlexServer] = None
        try:
            # plexapi.server.PlexServer can take requests.Session() object for custom configurations
            # For simplicity, we'll let it create its own.
            self.server = PlexServer(self.plex_url, self.plex_token)
            # Test connection by fetching server identifier or version
            self.logger.info(f"Successfully connected to Plex server: {self.server.friendlyName} (Version: {self.server.version})")
        except Unauthorized:
            self.logger.error(f"Plex connection unauthorized: Invalid token or insufficient permissions for {self.plex_url}.")
            self.server = None # Ensure server is None if connection failed
        except requests.exceptions.ConnectionError as e: # plexapi might raise this via requests
            self.logger.error(f"Plex connection failed for {self.plex_url}: {e}")
            self.server = None
        except Exception as e: # Catch any other plexapi or general exceptions during init
            self.logger.error(f"Failed to initialize Plex server connection to {self.plex_url}: {e}", exc_info=True)
            self.server = None

    def get_users(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all managed Plex accounts (users under the main account).

        Returns:
            Optional[List[Dict[str, Any]]]: List of user account objects as dictionaries, 
                                             or None if an error occurs or server not connected.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get users.")
            return None
        try:
            accounts: List[SystemAccount] = self.server.systemAccounts()
            user_list = []
            for acc in accounts:
                if acc.id != 0:
                    user_list.append({
                        "id": str(acc.id), 
                        "name": acc.name, 
                        "thumb": acc.thumb
                    })
            return user_list
        except Exception as e:
            self.logger.error(f"Error fetching Plex users: {e}", exc_info=True)
            return None

    def get_user_by_name(self, plex_username: str) -> Optional[Dict[str, Any]]:
        """
        Looks up a managed Plex user account ID using the provided username.

        Returns:
            Optional[Dict[str, Any]]: The user account object if found, or None.
        """
        users = self.get_users() # This already returns list of dicts
        if users:
            for user_dict in users:
                if user_dict.get("name") == plex_username:
                    return user_dict
        self.logger.info(f"User '{plex_username}' not found among managed accounts.")
        return None

    def get_recently_watched(self, plex_user_id: str, limit: Optional[int] = None, to_json_output: bool = False) -> Optional[List[Any]]:
        """
        Retrieves recently watched items from Plex for a specific user ID.

        Args:
            plex_user_id (str): The ID of the Plex user (from /accounts).
            limit (int, optional): The maximum number of items to retrieve. Defaults to the class default.
            to_json_output (bool, optional): If True, returns a list of dictionaries. 
                                             Otherwise, returns a list of plexapi objects. Defaults to False.

        Returns:
            Optional[List[Any]]: A list of recently watched items.
                                 If to_json_output is True, List[Dict[str, Any]].
                                 Otherwise, List[plexapi.video.MovieHistory or plexapi.video.EpisodeHistory].
                                 Returns None on error or if server not connected.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get recently watched.")
            return None
        if not plex_user_id:
            self.logger.error("Plex User ID is required for get_recently_watched.")
            return None
        
        try:
            user_id_int = int(plex_user_id)
        except ValueError:
            self.logger.error(f"Invalid Plex User ID format: {plex_user_id}. Must be an integer.")
            return None

        current_limit = limit if limit is not None else self.limit
        
        try:
            history_items: List[Media] = self.server.history(accountID=user_id_int, maxresults=current_limit)
            #self.logger.debug(f"{pprint(history_items)}")
            
            watched_videos = [item for item in history_items if isinstance(item, (MovieHistory, EpisodeHistory))]
            if to_json_output:
                return json.loads(toJson(watched_videos)) if watched_videos else []
            return watched_videos
        except NotFound:
            self.logger.info(f"No watch history found for user ID {plex_user_id}.")
            return [] # Return empty list for NotFound, consistent for both output types
        except Exception as e:
            self.logger.error(f"Error fetching recently watched for user ID {plex_user_id}: {e}", exc_info=True)
            return None
    
    def get_favorites(self, plex_user_id: str, limit: Optional[int] = None, to_json_output: bool = False) -> Optional[List[Any]]:
        """
        Retrieves "favorite" items (highly rated: 9 or 10 out of 10) for the user associated with the token.
        The plex_user_id is for logging/context, as ratings are tied to the token owner.

        Args:
            plex_user_id (str): The ID of the Plex user (for context).
            limit (int, optional): The maximum number of items to retrieve. Defaults to the class default.
            to_json_output (bool, optional): If True, returns a list of dictionaries. 
                                             Otherwise, returns a list of plexapi objects. Defaults to False.

        Returns:
            Optional[List[Any]]: List of "favorite" items.
                                 If to_json_output is True, List[Dict[str, Any]].
                                 Otherwise, List[plexapi.video.Movie or plexapi.video.Show].
                                 Returns None on error or server not connected.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get favorites.")
            return None
            
        self.logger.info(f"Fetching favorites (highly rated items) for user context (token dependent). User ID hint: {plex_user_id}")
        current_limit = limit if limit is not None else self.limit
        favorites: List[Union[Movie, Show]] = []

        try:
            for section in self.server.library.sections():
                if section.type in ['movie', 'show']:
                    self.logger.debug(f"Searching for favorites in section: {section.title} (Type: {section.type})")
                    items_in_section = section.all() 
                    
                    for item in items_in_section:
                        if len(favorites) >= current_limit:
                            break
                        if hasattr(item, 'userRating') and item.userRating is not None and item.userRating >= 9.0:
                            if isinstance(item, (Movie, Show)): 
                                favorites.append(item)
                    
                    if len(favorites) >= current_limit:
                        break 
            result_favorites = favorites[:current_limit]
            if to_json_output:
                return json.loads(toJson(result_favorites)) if result_favorites else []
            return result_favorites
        except Exception as e:
            self.logger.error(f"Error fetching favorites: {e}", exc_info=True)
            return None

    def get_items_filtered(self, items: Optional[List[Any]], source_type: str = "library", attribute_filter: Optional[str] = None) -> Any:
        """
        Filters Plex items (plexapi objects), consolidating episodes under series and ensuring uniqueness.
        Updates to the most recent last_played_date if duplicates are found (for history source).

        Args:
            items (Optional[List[Any]]): List of raw plexapi objects (e.g., Movie, Show, EpisodeHistory, MovieHistory).
            source_type (str): Describes the origin of items ('history', 'library_favorites', 'library_all').
                               'history' expects items to be MovieHistory or EpisodeHistory.
                               'library_favorites' or 'library_all' expects Movie or Show.
            attribute_filter (Optional[str]): If 'name', returns a list of names. Otherwise, List[ItemsFiltered].

        Returns:
            Union[List[ItemsFiltered], List[str]]: Filtered items. Empty list if input is None/empty.
        """
        if not items:
            self.logger.debug(f"No Plex items provided for filtering (source: {source_type}). Returning empty list.")
            return []

        processed_media_map: Dict[str, ItemsFiltered] = {}

        for item in items:
            media_name: Optional[str] = None
            consolidated_media_id: Optional[str] = None 
            output_media_type: Optional[str] = None  # 'movie' or 'tv'
            
            current_last_played_date_iso: Optional[str] = None
            play_count_val: Optional[int] = None
            is_favorite_val: Optional[bool] = None
            
            if source_type == "history":
                # Item is plexapi.video.Movie or plexapi.video.Episode
                if isinstance(item, EpisodeHistory):
                    media_name = item.grandparentTitle
                    consolidated_media_id = str(item.grandparentRatingKey)
                    output_media_type = "tv"
                    current_last_played_date_iso = _datetime_to_iso(item.viewedAt)
                elif isinstance(item, MovieHistory):
                    media_name = item.title
                    consolidated_media_id = str(item.ratingKey)
                    output_media_type = "movie"
                    current_last_played_date_iso = _datetime_to_iso(item.viewedAt)
                else:
                    self.logger.debug(f"Skipping history item with unhandled plexapi type '{type(item).__name__}': {getattr(item, 'title', 'Unknown Item')}")
                    continue
            
            elif source_type in ["library_favorites", "library_all"]:
                # Item is plexapi.video.Movie or plexapi.video.Show
                if isinstance(item, Show):
                    media_name = item.title
                    consolidated_media_id = str(item.ratingKey)
                    output_media_type = "tv"
                elif isinstance(item, Movie):
                    media_name = item.title
                    consolidated_media_id = str(item.ratingKey)
                    output_media_type = "movie"
                else:
                    self.logger.debug(f"Skipping library item with unhandled plexapi type '{type(item).__name__}': {getattr(item, 'title', 'Unknown Item')}")
                    continue

                play_count_val = item.viewCount if hasattr(item, 'viewCount') else None
                if hasattr(item, 'userRating') and item.userRating is not None:
                    is_favorite_val = item.userRating >= 9.0
                if hasattr(item, 'lastViewedAt'):
                     current_last_played_date_iso = _datetime_to_iso(item.lastViewedAt)
            else:
                self.logger.warning(f"Unknown source_type for Plex item filtering: {source_type}")
                continue

            if not media_name:
                self.logger.debug(f"Skipping item due to missing name (media_name is None): {item}")
                continue

            if media_name in processed_media_map:
                existing_pm_item = processed_media_map[media_name]
                if current_last_played_date_iso and source_type == "history": # Only update last played for history items
                    if not existing_pm_item.last_played_date or current_last_played_date_iso > existing_pm_item.last_played_date:
                        existing_pm_item.last_played_date = current_last_played_date_iso
                
                if play_count_val is not None and existing_pm_item.play_count is None: # Only set if not already set
                    existing_pm_item.play_count = play_count_val
                if is_favorite_val is not None and existing_pm_item.is_favorite is None: # Only set if not already set
                    existing_pm_item.is_favorite = is_favorite_val
            else:
                processed_media_map[media_name] = ItemsFiltered(
                    name=media_name,
                    id=consolidated_media_id,
                    type=output_media_type,
                    last_played_date=current_last_played_date_iso,
                    play_count=play_count_val,
                    is_favorite=is_favorite_val,
                )

        if attribute_filter and attribute_filter.lower() == "name":
            return [pm_item.name for pm_item in processed_media_map.values()]
        else:
            return list(processed_media_map.values())

    def get_all_items(self, to_json_output: bool = False) -> Optional[List[Any]]:
        """
        Retrieves all movie and TV show (series) items from the Plex library.

        Args:
            to_json_output (bool, optional): If True, returns a list of dictionaries. 
                                             Otherwise, returns a list of plexapi objects. Defaults to False.
        Returns:
            Optional[List[Any]]: List of all movie and show items.
                                 If to_json_output is True, List[Dict[str, Any]].
                                 Otherwise, List[plexapi.video.Movie or plexapi.video.Show].
                                 Returns None on error or server not connected.
        """
        if not self.server:
            self.logger.warning("Plex server not connected. Cannot get all items.")
            return None
            
        all_media_items: List[Union[Movie, Show]] = []
        try:
            for section in self.server.library.sections():
                if section.type == 'movie':
                    self.logger.debug(f"Fetching all movies from section: {section.title}")
                    all_media_items.extend(section.all()) # type: ignore # section.all() returns List[Movie]
                elif section.type == 'show':
                    self.logger.debug(f"Fetching all shows from section: {section.title}")
                    all_media_items.extend(section.all()) # type: ignore # section.all() returns List[Show]
            
            if to_json_output:
                return json.loads(toJson(all_media_items)) if all_media_items else []
            return all_media_items
        except Exception as e:
            self.logger.error(f"Error fetching all items from Plex library: {e}", exc_info=True)
            return None

    def get_all_items_filtered(self, attribute_filter: Optional[str] = None, to_json_output: bool = False) -> Optional[List[Any]]:
        """
        Retrieves all movie/show items from Plex and filters them using get_items_filtered.

        Args:
            attribute_filter (Optional[str]): If 'name', returns a list of names. 
                                              Otherwise, list of ItemsFiltered.

        Returns:
            Optional[List[Any]]: Filtered list (ItemsFiltered or str names) or None on error.
        """
        # Always fetch raw plex objects for filtering, regardless of any to_json_output on this method
        raw_plex_objects = self.get_all_items(to_json_output=False) 
        
        if raw_plex_objects is None: 
            self.logger.warning("No items returned from Plex library (error state or not connected) for get_all_items_filtered.")
            return None
        
        self.logger.debug(f"Retrieved {len(raw_plex_objects)} raw plexapi objects from library for filtering.")
        raw_plex_objects_filtered = self.get_items_filtered(items=raw_plex_objects, source_type="library_all", attribute_filter=attribute_filter)
        if to_json_output:
            return json.loads(toJson(raw_plex_objects_filtered)) if raw_plex_objects_filtered else []
        else: 
            return raw_plex_objects_filtered
