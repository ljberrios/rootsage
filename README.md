# RootSage

A capstone project web application for monitoring soil nutrient levels through sensor data.

## About

RootSage is an academic project developed as part of a capstone course. It demonstrates a full-stack web application that collects, processes, and displays soil nutrient data from NPK sensors, using machine learning models to classify nutrient levels.

*Note: This is an experimental project developed for educational purposes.*

## Features

### API
- Register NPK sensors with metadata
- Add crop information
- Record NPK sensor readings
- Retrieve latest sensor data

### Backend
- Flask-based server with SQLite database
- Machine learning classifiers for NPK level categorization
- User authentication with Argon2 password hashing
- Environment-based configuration

### Frontend
- Bootstrap 5 for responsive UI
- HTMX for dynamic content updates
- Real-time sensor data display
- Basic sensor management interface

## Setup

1. Clone the repository
2. Set required configuration values in one of these ways:
   - Create a `.env` file in the parent directory:
     ```
     ROOTSAGE_SECRET_KEY=your-secret-key
     ROOTSAGE_API_KEY=your-api-key
     ```
   - Set environment variables with the ROOTSAGE_ prefix
   - Create a config.json file (optional)

3. Install dependencies (requires Python 3.13+):
   ```
   poetry install
   ```

The application will create and initialize the database automatically on first run.

## Configuration

The application uses a hierarchical configuration system:

1. Default config from `config.py` classes
2. Environment variables prefixed with `ROOTSAGE_`
3. Optional `config.json` in root directory

Available settings:
- `SECRET_KEY`: Flask session encryption key
- `API_KEY`: Authentication key for API endpoints
- `DB_NAME`: SQLite database path (default: rootsage/app.db)
- `LOGS_DIR`: Directory for log files (default: rootsage/logs/)
- `LOG_LEVEL`: Python logging level (default: DEBUG in development)

## Technical Notes

### Current Implementation

- Supports basic NPK (Nitrogen, Phosphorus, Potassium) sensor data
- Simple ML models for nutrient level classification
- Basic user authentication
- SQLite for data persistence
- Rotating file logs

### Known Limitations

- NPK sensor accuracy varies significantly with soil conditions
- Basic ML models may need calibration for different environments
- Single-user system
- No data visualization or export features
- Limited error handling
- No input validation on sensor data ranges

### Potential Improvements

While this project serves its academic purpose, several improvements could be made for production use:

1. Data Collection
   - Support for additional sensor types (pH, moisture, temperature)
   - Sensor calibration interface
   - Data validation and cleaning
   - Automated sensor discovery

2. Analysis
   - Advanced ML model training
   - Time series analysis
   - Nutrient trend visualization
   - Crop-specific recommendations
   - Data export functionality

3. System
   - Multi-user support
   - Better API security
   - Documentation
   - Unit tests
   - Docker containerization

## License

MIT License - See LICENSE.txt for details

## Academic Context

This project was developed as part of a capstone course at the University of Puerto Rico. Its primary goal is to demonstrate full-stack web development, basic ML implementation, and IoT data processing concepts.