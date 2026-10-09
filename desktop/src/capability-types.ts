export interface WeatherLocation {
  label: string;
  latitude: number;
  longitude: number;
  timezone: string;
}
export interface ReadRoot {
  id: string;
  label: string;
  path: string;
}
export interface Capabilities {
  weather_provider: 'open-meteo';
  weather_location: WeatherLocation | null;
  system_available: boolean;
  read_roots: ReadRoot[];
}
