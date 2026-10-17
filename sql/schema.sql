CREATE TABLE IF NOT EXISTS weather_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    city VARCHAR(100) NOT NULL,
    observation_date DATE NOT NULL,
    temperature_2m_max DECIMAL(5, 2) NOT NULL,
    temperature_2m_min DECIMAL(5, 2) NOT NULL,
    precipitation_sum DECIMAL(6, 2) NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_city_date (city, observation_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
