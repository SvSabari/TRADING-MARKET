-- ========================================================
-- TRADERS PRO - Complete MySQL Database Schema (DDL)
-- Run this script or import into phpMyAdmin / MySQL CLI:
-- mysql -u <username> -p algo_trading_db < schema.sql
-- ========================================================

CREATE DATABASE IF NOT EXISTS algo_trading_db;
USE algo_trading_db;

CREATE TABLE backtest_runs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	strategy_kind VARCHAR(100), 
	symbol VARCHAR(100), 
	period_days INTEGER, 
	metrics JSON, 
	equity_curve JSON, 
	trades_log JSON, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE broker_connections (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	broker VARCHAR(50), 
	is_data_feed BOOLEAN, 
	is_order_exec BOOLEAN, 
	mock_mode BOOLEAN, 
	connected BOOLEAN, 
	credentials JSON, 
	access_token TEXT, 
	session_date VARCHAR(50), 
	PRIMARY KEY (id)
);

CREATE TABLE idempotency (
	id INTEGER NOT NULL, 
	user_id VARCHAR(36), 
	key VARCHAR(255), 
	signal_id VARCHAR(36), 
	created_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE managed_users (
	id VARCHAR(36) NOT NULL, 
	trader_id VARCHAR(36), 
	name VARCHAR(255), 
	email VARCHAR(255), 
	max_allocation FLOAT, 
	is_active BOOLEAN, 
	auto_copy BOOLEAN, 
	place_order BOOLEAN, 
	account_status VARCHAR(50), 
	phone VARCHAR(20), 
	password_hash VARCHAR(255), 
	profit_pct FLOAT, 
	bank_account VARCHAR(100), 
	brokers JSON, 
	symbol_multipliers JSON, 
	capital_allocation_pct FLOAT, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE market_candles (
	id INTEGER NOT NULL, 
	symbol VARCHAR(100), 
	timeframe VARCHAR(20), 
	ts DATETIME, 
	open FLOAT, 
	high FLOAT, 
	low FLOAT, 
	close FLOAT, 
	volume INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	kind VARCHAR(50), 
	title VARCHAR(255), 
	message VARCHAR(1000), 
	severity VARCHAR(20), 
	read BOOLEAN, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE option_candles (
	id INTEGER NOT NULL, 
	symbol VARCHAR(100), 
	strike FLOAT, 
	opt_type VARCHAR(10), 
	expiry VARCHAR(50), 
	ts DATETIME, 
	ltp FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE orders (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	broker VARCHAR(50), 
	broker_order_id VARCHAR(100), 
	symbol VARCHAR(100), 
	side VARCHAR(20), 
	qty INTEGER, 
	price FLOAT, 
	order_type VARCHAR(50), 
	product VARCHAR(50), 
	status VARCHAR(50), 
	source VARCHAR(50), 
	signal_id VARCHAR(36), 
	placed_at DATETIME, 
	filled_at DATETIME, 
	pnl FLOAT, 
	target FLOAT, 
	stop_loss FLOAT, 
	is_bracket BOOLEAN, 
	reject_reason VARCHAR(255), 
	is_mock BOOLEAN, 
	PRIMARY KEY (id)
);

CREATE TABLE poi_snapshots (
	date VARCHAR(20) NOT NULL, 
	oi_data JSON, 
	close_data JSON, 
	updated_at VARCHAR(50), 
	PRIMARY KEY (date)
);

CREATE TABLE positions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	symbol VARCHAR(100), 
	qty INTEGER, 
	avg_price FLOAT, 
	last_price FLOAT, 
	updated_at DATETIME, 
	is_mock BOOLEAN, 
	PRIMARY KEY (id)
);

CREATE TABLE push_settings (
	user_id VARCHAR(36) NOT NULL, 
	enabled BOOLEAN, 
	PRIMARY KEY (user_id)
);

CREATE TABLE push_tokens (
	id INTEGER NOT NULL, 
	user_id VARCHAR(36), 
	token VARCHAR(1000), 
	platform VARCHAR(50), 
	PRIMARY KEY (id)
);

CREATE TABLE strategies (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	name VARCHAR(100), 
	kind VARCHAR(50), 
	enabled BOOLEAN, 
	copy_to_users BOOLEAN, 
	params JSON, 
	symbols JSON, 
	fire_count INTEGER, 
	last_fire_at VARCHAR(50), 
	created_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE symbol_master (
	symbol VARCHAR(100) NOT NULL, 
	lot_size INTEGER, 
	exchange VARCHAR(50), 
	PRIMARY KEY (symbol)
);

CREATE TABLE telegram_settings (
	user_id VARCHAR(36) NOT NULL, 
	bot_token VARCHAR(1000), 
	chat_id VARCHAR(100), 
	enabled BOOLEAN, 
	PRIMARY KEY (user_id)
);

CREATE TABLE tv_signals (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	symbol VARCHAR(100), 
	side VARCHAR(10), 
	price FLOAT, 
	qty INTEGER, 
	strategy VARCHAR(100), 
	payload JSON, 
	received_at DATETIME, 
	processed BOOLEAN, 
	order_id VARCHAR(36), 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role VARCHAR(50), 
	PRIMARY KEY (id), 
	UNIQUE (email)
);

