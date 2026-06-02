-- Empresa B — Serviços Digitais
-- CRM SaaS customizado; cadastro focado em canais digitais (sem endereço/CPF).

CREATE TABLE IF NOT EXISTS clients (
    client_id        INT AUTO_INCREMENT PRIMARY KEY,
    full_name        VARCHAR(255) NOT NULL,
    email            VARCHAR(255) NOT NULL,
    phone            VARCHAR(30),
    instagram_handle VARCHAR(60),
    twitter_handle   VARCHAR(60),
    facebook_url     VARCHAR(255),
    preferred_channel ENUM('email', 'whatsapp', 'instagram', 'twitter') DEFAULT 'email',
    signup_date      DATE NOT NULL,
    last_active      DATETIME,
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
