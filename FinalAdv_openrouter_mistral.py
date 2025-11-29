import tkinter as tk
from tkinter import messagebox, ttk
import openai
import threading
import queue
from google.maps import places_v1
import googlemaps
from google.type import latlng_pb2
from tkintermapview import TkinterMapView


MY_GOOGLE_MAPS_KEY ="Your_Google_Maps_Key_HERE"
MY_OPENROUTER_KEY = "Your_OpenRouter_Key_HERE"
MY_OPENAI_KEY = "YOUR_OPENAI_KEY_HERE"

class FuelTrack(tk.Tk):
    def __init__(self):
        super().__init__()

        # --- API Clients Setup ---
        self.api_queue = queue.Queue()
        self.google_client = None
        self.gmaps_client = None
        self.openai_client = None
        self.ai_enabled = False
        self.google_api_enabled = False

        self.setup_api_clients()

        # --- Window and Variable Setup ---
        self.title('FuelTrack - Live Price Map')
        # Updated geometry for the map
        self.geometry('900x650')
        self.resizable(True, True)  # Make window resizable

        self.radio_var = tk.StringVar(value="Gasoline")
        self.station_var = tk.StringVar()
        self.current_station_prices = {}
        self.current_map_markers = []  # To keep track of markers

        # --- Configure Grid Layout ---
        # We will have two columns:
        # Column 0: Control Panel (fixed width)
        # Column 1: Map (expands)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Create UI ---
        # Create a frame for the left-side control panel
        self.control_panel = ttk.Frame(self, padding=10)
        self.control_panel.grid(row=0, column=0, sticky="nsew")

        # Create the widgets *inside* the control panel frame
        self.create_widgets(self.control_panel)

        # Create the map widget on the right
        self.create_map_widget(self)

    def setup_api_clients(self):
        """Configure AI and Google Maps API clients (same as your original)"""
        try:
            self.openai_client = openai.OpenAI(
                api_key=MY_OPENROUTER_KEY,
                base_url="https://openrouter.ai/api/v1"
            )
            self.ai_enabled = True
        except Exception as e:
            self.ai_enabled = False
            print(f"AI configuration failed: {e}")

        try:
            google_api_key = MY_GOOGLE_MAPS_KEY
            if not google_api_key or google_api_key == "YOUR_GOOGLE_MAPS_KEY_HERE":
                raise ValueError("Google API key is not set in the script")

            self.google_client = places_v1.PlacesClient(client_options={"api_key": google_api_key})
            self.gmaps_client = googlemaps.Client(key=google_api_key)
            self.google_api_enabled = True
        except Exception as e:
            self.google_api_enabled = False
            print(f"Google Maps API configuration failed: {e}")
            messagebox.showerror("Google API Error", f"Failed to initialize Google Maps client: {e}")

    def create_widgets(self, parent_frame):
        """Create all UI components within the parent_frame"""
        title_label = tk.Label(
            parent_frame,
            text='FuelTrack',
            font=('Helvetica', 16, 'bold'),
            fg='dark blue'
        )
        title_label.grid(column=0, row=0, columnspan=2, pady=10, padx=10)

        # --- Search Section ---
        self.create_search_section(parent_frame)

        # --- Existing Sections ---
        self.create_fuel_type_section(parent_frame)
        self.create_mpg_section(parent_frame)
        self.create_gas_station_section(parent_frame)
        self.create_action_buttons(parent_frame)

    def create_search_section(self, parent_frame):
        """Create a search box and button"""
        search_frame = ttk.LabelFrame(parent_frame, text="Search Location", padding=10)
        search_frame.grid(column=0, row=1, columnspan=2, padx=10, pady=5, sticky='we')

        self.search_entry = ttk.Entry(search_frame, width=28)
        self.search_entry.grid(column=0, row=0, padx=5, sticky='we')

        # Bind the <Return> key to the search function
        self.search_entry.bind("<Return>", self.start_map_search)

        self.search_button = ttk.Button(
            search_frame,
            text="Search",
            command=self.start_map_search
        )
        self.search_button.grid(column=1, row=0, padx=5)

        # Make the entry box expand with the panel
        search_frame.grid_columnconfigure(0, weight=1)

    def create_fuel_type_section(self, parent_frame):
        """Create fuel type selection (added parent_frame)"""
        fuel_frame = ttk.LabelFrame(parent_frame, text="Fuel Type", padding=10)
        fuel_frame.grid(column=0, row=2, columnspan=2, padx=10, pady=5, sticky='we')
        self.rb_gasoline = ttk.Radiobutton(
            fuel_frame, text='Gasoline', variable=self.radio_var,
            value="Gasoline", command=self.clear_station_cache
        )
        self.rb_gasoline.grid(column=0, row=0, padx=5)
        self.rb_diesel = ttk.Radiobutton(
            fuel_frame, text='Diesel', variable=self.radio_var,
            value="Diesel", command=self.clear_station_cache
        )
        self.rb_diesel.grid(column=1, row=0, padx=5)

        fuel_frame.grid_columnconfigure(0, weight=1)
        fuel_frame.grid_columnconfigure(1, weight=1)

    def create_mpg_section(self, parent_frame):
        """Create MPG input section"""
        mpg_frame = ttk.LabelFrame(parent_frame, text="Vehicle Efficiency", padding=10)
        mpg_frame.grid(column=0, row=3, columnspan=2, padx=10, pady=5, sticky='we')
        mpg_label = ttk.Label(mpg_frame, text='Vehicle MPG:')
        mpg_label.grid(column=0, row=0, padx=5)
        self.mpg_entry = ttk.Entry(mpg_frame, width=15)
        self.mpg_entry.grid(column=1, row=0, padx=5)

        mpg_frame.grid_columnconfigure(1, weight=1)

    def create_gas_station_section(self, parent_frame):
        """Create gas station selection"""
        station_frame = ttk.LabelFrame(parent_frame, text="Select Gas Station", padding=10)
        station_frame.grid(column=0, row=4, columnspan=2, padx=10, pady=5, sticky='we')
        station_label = ttk.Label(station_frame, text='Available Stations:')
        station_label.grid(column=0, row=0, padx=5)
        self.gas_station_combobox = ttk.Combobox(
            station_frame, textvariable=self.station_var,
            state="disabled", width=22
        )
        self.gas_station_combobox.grid(column=0, row=1, columnspan=2, padx=5, pady=5, sticky='we')

        station_frame.grid_columnconfigure(0, weight=1)

    def create_action_buttons(self, parent_frame):
        """Create action buttons"""
        button_frame = ttk.Frame(parent_frame, padding=10)
        button_frame.grid(column=0, row=5, columnspan=2, pady=10)

        self.calc_button = ttk.Button(
            button_frame, text="Calculate Cost",
            command=self.show_price, width=15
        )
        self.calc_button.grid(column=0, row=0, padx=10)

        self.ai_button = ttk.Button(
            button_frame, text="Get Fuel Tips",
            command=self.get_ai_recommendations, width=15
        )
        self.ai_button.grid(column=1, row=0, padx=10)
        if not self.ai_enabled:
            self.ai_button.config(state='disabled')

        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

    def create_map_widget(self, parent_frame):
        """Create the map widget on the right side"""
        self.map_widget = TkinterMapView(parent_frame, width=600, height=600, corner_radius=10)
        self.map_widget.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Set a default position (e.g., New Britain, CT)
        self.map_widget.set_position(41.6612, -72.7798)
        self.map_widget.set_zoom(12)

    def clear_station_cache(self):
        """Clears station data when fuel type changes."""
        self.current_station_prices = {}
        self.station_var.set("")
        self.gas_station_combobox.config(values=[], state="disabled")
        # If a search is already active, re-trigger it
        if self.search_entry.get():
            self.start_map_search()

    def start_map_search(self, event=None):
        """
        Disables UI and starts the API search from the search_entry.
        """
        if not self.google_api_enabled:
            messagebox.showerror("API Error", "Google Maps API client is not initialized.")
            return

        search_query = self.search_entry.get().strip()
        if not search_query:
            messagebox.showwarning("Input Error", "Please enter a location to search.")
            return

        fuel_type = self.radio_var.get()

        # Update UI to show loading state
        self.station_var.set("Searching...")
        self.gas_station_combobox.config(state="disabled")
        self.calc_button.config(state="disabled")
        self.search_button.config(state="disabled", text="...")
        self.update_idletasks()

        # Start the background thread
        threading.Thread(
            target=self.run_map_search_and_geocode,
            args=(search_query, fuel_type),
            daemon=True
        ).start()

        self.after(100, self.check_api_queue)

    def run_map_search_and_geocode(self, search_query, fuel_type):
        """
        Runs on a background thread.
        1. Geocodes the search query to get coordinates.
        2. Fetches stations from Google Places API.
        3. Gathers locations and prices.
        4. Puts *all* data into the queue.
        """
        try:
            # --- Geocode the search query to get coordinates ---
            geocode_result = self.gmaps_client.geocode(search_query)
            if not geocode_result:
                raise ValueError(f"Could not find coordinates for '{search_query}'")

            location = geocode_result[0]['geometry']['location']
            center_lat = location['lat']
            center_lng = location['lng']

            # --- Use coordinates to call search_nearby ---
            google_fuel_type = "REGULAR_UNLEADED"
            if fuel_type == "Diesel":
                google_fuel_type = "DIESEL"

            center_point = latlng_pb2.LatLng(latitude=center_lat, longitude=center_lng)
            search_circle = places_v1.types.geometry.Circle(center=center_point, radius=5000.0)  # 5km
            location_restriction = places_v1.SearchNearbyRequest.LocationRestriction(circle=search_circle)

            # Ask for the place name (resource id)
            search_request = places_v1.SearchNearbyRequest(
                location_restriction=location_restriction,
                included_types=["gas_station"],
                rank_preference="DISTANCE",
            )
            search_field_mask = "places.name"
            search_metadata = (('x-goog-fieldmask', search_field_mask),)
            response = self.google_client.search_nearby(request=search_request, metadata=search_metadata)

            # --- Get Details (including location) for Each Place ---

            # Ask for displayName, fuelOptions, AND location
            details_field_mask = "displayName,fuelOptions,location"
            details_metadata = (('x-goog-fieldmask', details_field_mask),)

            stations_data = {}  # For the combobox {name: price}
            station_locations = []  # For the map pins [(lat, lng, name, price)]
            count = 0

            for place in response.places:
                if count >= 10:  # Limit to 10 results for the map
                    break

                if not place.name: continue

                details_request = places_v1.GetPlaceRequest(name=place.name)
                place_details = self.google_client.get_place(request=details_request, metadata=details_metadata)

                if place_details.fuel_options:
                    for fuel_price in place_details.fuel_options.fuel_prices:
                        if fuel_price.type_.name == google_fuel_type:
                            price = fuel_price.price.units + (fuel_price.price.nanos / 1_000_000_000)
                            station_name = place_details.display_name.text
                            station_lat = place_details.location.latitude
                            station_lng = place_details.location.longitude

                            stations_data[station_name] = round(price, 2)
                            station_locations.append((station_lat, station_lng, station_name, round(price, 2)))

                            count += 1
                            break

            # Put the complete data packet into the queue
            self.api_queue.put({
                "center_lat": center_lat,
                "center_lng": center_lng,
                "stations_data": stations_data,
                "station_locations": station_locations
            })

        except Exception as e:
            self.api_queue.put({"error": str(e)})

    def check_api_queue(self):
        """
        Checks queue for the new data packet and updates map + combobox.
        """
        try:
            result = self.api_queue.get(block=False)

            # Re-enable buttons
            self.calc_button.config(state="normal")
            self.search_button.config(state="normal", text="Search")

            if isinstance(result, dict) and "error" in result:
                messagebox.showerror("API Error", f"Could not fetch data: {result['error']}")
                self.station_var.set("API search failed")
                return

            if not result["station_locations"]:
                messagebox.showinfo(
                    "No Results",
                    f"No stations found with {self.radio_var.get()} prices in this area."
                )
                self.station_var.set("No prices found")
                self.gas_station_combobox.config(values=[], state="disabled")
                self.map_widget.delete_all_marker()
                # Still center the map on the searched location
                self.map_widget.set_position(result["center_lat"], result["center_lng"])
                self.map_widget.set_zoom(14)
                return

            # --- Process Successful Results ---

            # 1. Center the map on the searched location
            self.map_widget.set_position(result["center_lat"], result["center_lng"])
            self.map_widget.set_zoom(14)

            # 2. Clear old map markers
            self.map_widget.delete_all_marker()

            # 3. Populate the Combobox
            self.current_station_prices = result["stations_data"]
            station_names = list(self.current_station_prices.keys())
            self.gas_station_combobox.config(values=station_names, state='readonly')
            if station_names:
                self.station_var.set(station_names[0])
            else:
                self.station_var.set("No prices found")
                self.gas_station_combobox.config(state="disabled")

            # 4. Add new markers to the map
            for lat, lng, name, price in result["station_locations"]:
                pin_text = f"{name}\n${price:.2f}"
                self.map_widget.set_marker(
                    lat, lng,
                    text=pin_text,
                    command=self.on_marker_click  # <-- Add click command
                )

        except queue.Empty:
            self.after(100, self.check_api_queue)

    def on_marker_click(self, marker):
        """
      This function is called when a map pin is clicked.
        It selects the corresponding station in the combobox.
        """
        # The marker text is "Station Name\n$Price.XX"
        station_name = marker.text.split('\n')[0]

        # Check if this station is valid (it always should be)
        if station_name in self.current_station_prices:
            self.station_var.set(station_name)
            print(f"Map Clicked: Selected {station_name}")

    def show_price(self):
        """Calculate and display fuel cost information """
        try:
            town = self.search_entry.get().strip()
            if not town:
                raise IndexError("No town selected")

            station = self.station_var.get()
            if not station or station in ["Searching...", "No prices found", "API search failed"]:
                raise KeyError("No gas station selected")

            mpg_text = self.mpg_entry.get().strip()
            if not mpg_text:
                raise ValueError("MPG value is required")
            mpg = float(mpg_text)
            if mpg <= 0:
                raise ValueError("MPG must be greater than 0")

            fuel_type = self.radio_var.get()
            price = self.current_station_prices[station]
            cost_per_mile = price / mpg
            cost_per_100_miles = cost_per_mile * 100

            result_string = self.generate_result_string(
                station, town, fuel_type, price, mpg, cost_per_mile, cost_per_100_miles
            )
            messagebox.showinfo("Fuel Cost Calculation", result_string)

        except IndexError:
            messagebox.showerror("Input Error", "Please search for a location first.")
        except KeyError:
            messagebox.showerror("Input Error", "Please select a valid gas station (or search first).")
        except ValueError as e:
            if "MPG" in str(e):
                messagebox.showerror("Input Error", "Please enter a valid MPG number greater than 0.")
            else:
                messagebox.showerror("Input Error", str(e))

    def generate_result_string(self, station, town, fuel_type, price, mpg, cost_per_mile, cost_per_100_miles):
        """Generate formatted result string"""
        # Using a more generic "Area" instead of "Town"
        return f"""
Fuel Cost Analysis
{'-' * 40}

Station: {station} (Area: {town})
Fuel Type: {fuel_type}
Vehicle MPG: {mpg}

Price: ${price:.2f} per gallon
Cost per Mile: ${cost_per_mile:.3f}
Cost per 100 Miles: ${cost_per_100_miles:.2f}
"""

    def get_ai_recommendations(self):
        """Get AI-powered fuel saving recommendations"""
        if not self.ai_enabled:
            messagebox.showwarning("AI Service Unavailable", "AI recommendations are not available.")
            return
        try:
            fuel_type = self.radio_var.get()
            mpg_text = self.mpg_entry.get().strip()
            if not mpg_text:
                messagebox.showwarning("Input Required", "Please enter your vehicle's MPG.")
                return

            prompt = self.create_ai_prompt(fuel_type, mpg_text)
            self.ai_button.config(state='disabled', text="Loading...")
            self.update()

            response = self.openai_client.chat.completions.create(
                model="mistralai/mistral-7b-instruct:free",
                messages=[
                    {"role": "system", "content": "You are a fuel efficiency expert..."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=350, temperature=0.7
            )
            ai_tips = response.choices[0].message.content
            messagebox.showinfo("AI Fuel Efficiency Tips", f"Personalized Fuel-Saving Tips:\n\n{ai_tips}")

        except Exception as e:
            messagebox.showerror("AI Service Error", f"Could not get AI recommendations: {str(e)}")
        finally:
            self.ai_button.config(state='normal', text="Get Fuel Tips")

    def create_ai_prompt(self, fuel_type, mpg_text):
        """Create prompt for AI recommendations"""
        return f"""
Provide 4-5 practical fuel-saving tips for someone using {fuel_type} fuel.
Vehicle MPG: {mpg_text}
...
"""


def main():
    """Main function to run the application"""
    try:
        app = FuelTrack()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("Application Error", f"Failed to start application: {str(e)}")


if __name__ == '__main__':
    main()