import requests
import json
import logging
import sys  
from urllib.parse import urljoin
from typing import Optional, Dict, List, Any 
from .models import ItemsFiltered

class Jellyfin:
    """
    A class to interact with the Jellyfin API for user and media data.
    """

    def __init__(self, jellyfin_url: str, jellyfin_api_key: str, limit: int = 10):
        """
        Initializes the Jellyfin class with API configurations.

        Args:
            jellyfin_url (str): The base URL of the Jellyfin server.
            jellyfin_api_key (str): The API key for Jellyfin.
            jellyfin_username (str): The username of the Jellyfin user.
            limit (int): Default limit for API requests.
        """
        # Setup Logging
        self.logger = logging.getLogger(__name__)

        self.jellyfin_url = jellyfin_url
        self.jellyfin_api_key = jellyfin_api_key
        self.limit = limit

        self.jellyfin_auth = f"MediaBrowser Client='other', Device='my-script', DeviceId='some-unique-id', Version='0.0.0', Token={self.jellyfin_api_key}"

    def get_users(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all users

        Returns:
            Optional[List[Dict[str, Any]]]: List of user objects, or None if an error occurs.
        """
        endpoint = urljoin(self.jellyfin_url, "/Users")
        headers = {
            "Authorization": self.jellyfin_auth,
            "Content-Type": "application/json",
        }
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            users_data = response.json()
            return users_data
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error looking up Jellyfin user ID: {e}")
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON response from Jellyfin when looking up user ID.")
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred: {e}")
        return None

    def get_user_by_name(self, jellyfin_username: str) -> Optional[str]:
        """
        Looks up the Jellyfin user ID using the provided username.

        Returns:
            str: The Jellyfin user ID, or None on error.
        """
        endpoint = urljoin(self.jellyfin_url, "/Users")
        headers = {
            "Authorization": self.jellyfin_auth,
            "Content-Type": "application/json",
        }
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            users_data = response.json()
            # Iterate through the users to find the one with the matching username.
            for user in users_data:
                if user.get("Name") == jellyfin_username:
                    return user  # Return the user ID if found
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error looking up Jellyfin user ID: {e}")
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON response from Jellyfin when looking up user ID.")
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred: {e}")
        return None
    
    

    def get_recently_watched(self, jellyfin_user_id: str, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves recently watched items from the Jellyfin API.

        Args:
            limit (int, optional): The maximum number of items to retrieve. Defaults to the class default.

        Returns:
            list: A list of recently watched items (dictionaries) from the Jellyfin API, or None on error.
        """
        try:
            if not self.jellyfin_url or not self.jellyfin_api_key or not jellyfin_user_id:
                self.logger.error("Jellyfin URL, Key, and User ID are required.")
                return None

            limit = limit if limit is not None else self.limit  # Use provided limit or default

            endpoint = urljoin(self.jellyfin_url, f"/Users/{jellyfin_user_id}/Items")
            headers = {
                "Authorization": self.jellyfin_auth,
                "Content-Type": "application/json",
            }
            params = {
                "Limit": limit,
                "Recursive": "true",
                "Fields": "BasicSyncInfo,MediaSource",
                "IncludeItemTypes": "Movie,Episode",
                "SortBy": "DatePlayed",
                "SortOrder": "Descending",
                "IsPlayed": "true",
                "enableUserData": "true",
            }

            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            return response.json()["Items"]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Jellyfin request failed: {e}")
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON response from Jellyfin.")
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred: {e}")
        return None
    
    def get_favorites(self, jellyfin_user_id: str, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves favorite items from the Jellyfin API for a specific user.

        Args:
            jellyfin_user_id (str): The ID of the Jellyfin user.
            limit (int, optional): The maximum number of items to retrieve. Defaults to the class default.

        Returns:
            Optional[List[Dict[str, Any]]]: A list of favorite items (dictionaries) 
                                             from the Jellyfin API, or None on error.
        """
        try:
            if not self.jellyfin_url or not self.jellyfin_api_key or not jellyfin_user_id:
                self.logger.error("Jellyfin URL, API Key, and User ID are required for get_favorites.")
                return None

            endpoint = urljoin(self.jellyfin_url, f"/Users/{jellyfin_user_id}/Items")
            headers = {
                "Authorization": self.jellyfin_auth,
                "Content-Type": "application/json",
            }
            params = {
                "Limit": limit,
                "Recursive": "true",
                "Fields": "BasicSyncInfo,MediaSource", # Adjust fields as needed for favorites
                "IncludeItemTypes": "Movie,Series", # Add or remove types as needed
                "IsFavorite": "true",
                "SortBy": "SortName", # Or DateCreated, CommunityRating, etc.
                "SortOrder": "Ascending",
                "enableUserData": "true", # Important to check UserData.IsFavorite
            }
            self.logger.debug(f"Jellyfin get_favorites endpoint: {endpoint}")
            self.logger.debug(f"Jellyfin get_favorites params: {params}")

            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            return response.json()["Items"]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Jellyfin get_favorites request failed: {e}")
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON response from Jellyfin in get_favorites.")
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred in get_favorites: {e}")
        return None

    def get_items_filtered(self, items: Optional[List[Dict[str, Any]]], item_type: Optional[any] = None, attribute_filter: Optional[str] = None, source_type: Optional[str] = None) -> Any:
        """
        Filters recently watched items, ensuring uniqueness by media name (movie or series)
        and updating to the most recent last_played_date if duplicates are found.
        For episodes, it consolidates them under their series name.

        Args:
            items (Optional[List[Dict[str, Any]]]): 
                List of raw item dictionaries from Jellyfin's get_recently_watched. 
                Can be None or empty.

        Returns:
            List[ItemsFiltered]: 
                A list of processed media items as ItemsFiltered objects.
                Returns an empty list if input items is None or empty.
        """
        if not items:
            self.logger.warning("No items provided for filtering. Returning empty list.")
            return []

        # Use a dictionary to store unique media items by name, ensuring the most recent play date.
        # Key: media_name (str)
        # Value: Dict[str, Any] (processed media item: {'name', 'id', 'type', 'last_played_date'})
        processed_media_map: Dict[str, ItemsFiltered] = {}

        for item in items:
            user_data = item.get("UserData", {})

            current_last_played_date_str = None
            play_count = 0
            is_favorite = False
            if user_data:
                current_last_played_date_str = user_data.get("LastPlayedDate")
                play_count = user_data.get("PlayCount", 0)
                is_favorite = user_data.get("IsFavorite", False)

            item_jellyfin_type = item.get("Type", "Unknown")  # "Movie", "Episode", etc.
            media_name: Optional[str] = None
            media_id: Optional[str] = None
            output_media_type: Optional[str] = None

            if item_jellyfin_type == "Episode":
                media_name = item.get("SeriesName")
                media_id = item.get("SeriesId")
                output_media_type = "tv"
            elif item_jellyfin_type == "Series":
                media_name = item.get("Name")
                media_id = item.get("Id")
                output_media_type = "tv"
            elif item_jellyfin_type == "Movie":
                media_name = item.get("Name")
                media_id = item.get("Id")
                output_media_type = "movie"
            else:
                self.logger.debug(f"Skipping item with unhandled type '{item_jellyfin_type}': {item.get('Name', 'Unknown Item')}")
                continue # Skip types we don't explicitly handle for consolidated history

            if not media_name:
                self.logger.debug(f"Skipping item due to missing name (media_name is None): {item}")
                continue

            if media_name in processed_media_map:
                existing_item = processed_media_map[media_name]
                if current_last_played_date_str:
                    # Dates are ISO 8601 strings; direct string comparison works for recency.
                    if current_last_played_date_str > existing_item.last_played_date:
                        existing_item.last_played_date = current_last_played_date_str
                        self.logger.debug(f"Updated last_played_date for '{media_name}' to {current_last_played_date_str}")
                else:
                    self.logger.debug(f"No last_played_date for '{media_name}'")
            else:
                processed_media_map[media_name] = ItemsFiltered(
                    name=media_name,
                    id=media_id,
                    type=output_media_type,
                    last_played_date=current_last_played_date_str,
                    play_count=play_count,
                    is_favorite=is_favorite
                )
                #self.logger.debug(f"Added new media '{media_name}' (Type: {output_media_type}, ID: {media_id}) with last_played_date {current_last_played_date_str}")

        if attribute_filter:
            # If attribute_filter is provided, filter the processed media map by that attribute
            names = [getattr(item, attribute_filter.lower(), "") for item in processed_media_map.values()]
            return names
            #return ",".join(names)
        else:
            return list(processed_media_map.values()) 
    
    def get_all_items(self) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieves all items from the Jellyfin API for the user, recursively.

        Returns:
            list: A list of all items (dictionaries) from the Jellyfin API, or None on error.
        """
        try:
            if not self.jellyfin_url or not self.jellyfin_api_key:
                self.logger.error("Jellyfin URL, Key, and User ID are required.")
                return None

            endpoint = urljoin(self.jellyfin_url, f"/Items")
            headers = {
                "Authorization": self.jellyfin_auth,
                "Content-Type": "application/json",
            }
            params = {
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Series", # Add or remove types as needed
            }

            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("Items", [])
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Jellyfin get_all_items request failed: {e}")
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON response from Jellyfin in get_all_items.")
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred in get_all_items: {e}")
        return None

    def get_all_items_filtered(self, attribute_filter: Optional[str] = None) -> Optional[List[Any]]:
        """
        Filters items by the "Type" field. Supports single or multiple types.

        Args:
            items (list): List of item dictionaries.
            item_type (str or list): The value(s) to filter by in the "Type" field.
            to_string (bool): If True, return a comma-delimited string of item names; if False, return full item dicts.

        Returns:
            list or str: Filtered list of items or a comma-delimited string of item names.
        """
        items = self.get_all_items()
        self.logger.debug(f"Retrieved {len(items) if items else 0} items from Jellyfin.")
        if items is None:
            self.logger.warning("No items returned from Jellyfin.")
            return None

        return self.get_items_filtered(items=items, attribute_filter=attribute_filter)
