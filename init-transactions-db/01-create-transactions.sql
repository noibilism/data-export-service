-- Create transactions database and user
CREATE DATABASE IF NOT EXISTS transactions;
CREATE USER IF NOT EXISTS 'readonly_user'@'%' IDENTIFIED BY 'readonly_password';
GRANT SELECT ON transactions.* TO 'readonly_user'@'%';
FLUSH PRIVILEGES;

USE transactions;

-- Create sample transactions table
CREATE TABLE IF NOT EXISTS bank_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    txn_date DATE NOT NULL,
    txn_time TIME NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    description TEXT,
    reference_number VARCHAR(100),
    transaction_type ENUM('DEBIT', 'CREDIT') NOT NULL,
    balance_after DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_txn_date (txn_date),
    INDEX idx_account_date (account_id, txn_date),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create another sample table for credit card transactions
CREATE TABLE IF NOT EXISTS credit_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    card_number VARCHAR(20) NOT NULL,
    txn_date DATE NOT NULL,
    txn_time TIME NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    merchant_name VARCHAR(255),
    merchant_category VARCHAR(100),
    authorization_code VARCHAR(50),
    transaction_type ENUM('PURCHASE', 'REFUND', 'CASH_ADVANCE') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_txn_date (txn_date),
    INDEX idx_card_date (card_number, txn_date),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert sample data for testing
INSERT INTO bank_transactions (account_id, txn_date, txn_time, amount, description, reference_number, transaction_type, balance_after) VALUES
('ACC001', '2024-01-01', '09:30:00', -50.00, 'ATM Withdrawal', 'ATM001234', 'DEBIT', 1950.00),
('ACC001', '2024-01-02', '14:15:00', 1500.00, 'Salary Deposit', 'SAL202401', 'CREDIT', 3450.00),
('ACC001', '2024-01-03', '10:45:00', -25.99, 'Online Purchase - Amazon', 'AMZ789012', 'DEBIT', 3424.01),
('ACC001', '2024-01-04', '16:20:00', -100.00, 'Utility Bill Payment', 'UTIL2024001', 'DEBIT', 3324.01),
('ACC001', '2024-01-05', '11:30:00', -75.50, 'Grocery Store', 'GRO456789', 'DEBIT', 3248.51),
('ACC002', '2024-01-01', '08:00:00', 2000.00, 'Initial Deposit', 'INIT001', 'CREDIT', 2000.00),
('ACC002', '2024-01-02', '12:30:00', -200.00, 'Rent Payment', 'RENT202401', 'DEBIT', 1800.00),
('ACC002', '2024-01-03', '15:45:00', -45.00, 'Gas Station', 'GAS123456', 'DEBIT', 1755.00),
('ACC002', '2024-01-04', '09:15:00', 500.00, 'Freelance Payment', 'FREE2024001', 'CREDIT', 2255.00),
('ACC002', '2024-01-05', '13:20:00', -30.00, 'Restaurant', 'REST789012', 'DEBIT', 2225.00);

INSERT INTO credit_transactions (card_number, txn_date, txn_time, amount, merchant_name, merchant_category, authorization_code, transaction_type) VALUES
('****1234', '2024-01-01', '10:30:00', 89.99, 'Best Buy', 'Electronics', 'AUTH001234', 'PURCHASE'),
('****1234', '2024-01-02', '14:15:00', 25.50, 'Starbucks', 'Food & Beverage', 'AUTH001235', 'PURCHASE'),
('****1234', '2024-01-03', '16:45:00', 150.00, 'Target', 'Department Store', 'AUTH001236', 'PURCHASE'),
('****1234', '2024-01-04', '11:20:00', -25.50, 'Starbucks', 'Food & Beverage', 'REF001235', 'REFUND'),
('****1234', '2024-01-05', '13:30:00', 75.00, 'Shell Gas Station', 'Gas Station', 'AUTH001237', 'PURCHASE'),
('****5678', '2024-01-01', '09:00:00', 200.00, 'Whole Foods', 'Grocery', 'AUTH002001', 'PURCHASE'),
('****5678', '2024-01-02', '12:45:00', 45.99, 'Netflix', 'Entertainment', 'AUTH002002', 'PURCHASE'),
('****5678', '2024-01-03', '17:30:00', 120.00, 'Uber', 'Transportation', 'AUTH002003', 'PURCHASE'),
('****5678', '2024-01-04', '10:15:00', 300.00, 'Cash Advance', 'ATM', 'CASH002001', 'CASH_ADVANCE'),
('****5678', '2024-01-05', '14:20:00', 65.00, 'Home Depot', 'Home Improvement', 'AUTH002004', 'PURCHASE');

-- Add more sample data for performance testing (optional)
-- This creates a larger dataset for testing export performance
DELIMITER //
CREATE PROCEDURE GenerateTestData()
BEGIN
    DECLARE i INT DEFAULT 0;
    DECLARE max_records INT DEFAULT 10000;
    
    WHILE i < max_records DO
        INSERT INTO bank_transactions (account_id, txn_date, txn_time, amount, description, reference_number, transaction_type, balance_after)
        VALUES (
            CONCAT('ACC', LPAD(FLOOR(RAND() * 100) + 1, 3, '0')),
            DATE_ADD('2024-01-01', INTERVAL FLOOR(RAND() * 365) DAY),
            TIME(CONCAT(LPAD(FLOOR(RAND() * 24), 2, '0'), ':', LPAD(FLOOR(RAND() * 60), 2, '0'), ':00')),
            ROUND((RAND() * 2000 - 1000), 2),
            CONCAT('Transaction ', i),
            CONCAT('REF', LPAD(i, 8, '0')),
            IF(RAND() > 0.5, 'CREDIT', 'DEBIT'),
            ROUND((RAND() * 10000), 2)
        );
        SET i = i + 1;
    END WHILE;
END//
DELIMITER ;

-- Uncomment the following line to generate test data
-- CALL GenerateTestData();