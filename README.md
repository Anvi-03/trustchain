# MyCoin

MyCoin is an educational cryptocurrency and blockchain simulator built with Django and PostgreSQL. It models the lifecycle of a simple coin transfer from wallet creation through digital signing, proof-of-work mining, block confirmation, and chain validation.

It runs entirely on a local database and uses simulated MYC balances. It does not connect to a cryptocurrency network or use real money.

## Features

- User registration, login, and logout using Django's built-in authentication
- One wallet per user with a SHA-256-derived address and RSA key pair
- RSA-PSS transaction signatures verified before a transfer enters the pending pool
- Pending and confirmed transaction history
- Automatic Genesis Block with index `0` and previous hash `0`
- SHA-256 block hashes and previous-hash links between blocks
- Proof-of-Work mining with a three-leading-zero difficulty target
- Atomic balance settlement, confirmation, block creation, and mining reward payment
- Blockchain explorer with block and transaction details
- Blockchain validation that identifies the first invalid block
- Responsive Bootstrap dashboard with a dark cryptocurrency-style interface

## Technology

| Area | Technology |
| --- | --- |
| Backend | Python and Django |
| Database | PostgreSQL |
| Cryptography | `cryptography`, RSA-PSS, SHA-256 |
| Frontend | Django templates, Bootstrap, CSS |
| Tests | Django test framework |

## Requirements

- Python 3.10 or later
- PostgreSQL 14 or later

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Anvi-03/trustchain.git
cd trustchain
```

### 2. Create a virtual environment and install dependencies

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 3. Create the PostgreSQL database

Open PostgreSQL's `psql` shell as an administrator and run:

```sql
CREATE ROLE mycoin LOGIN CREATEDB PASSWORD 'choose-a-local-password';
CREATE DATABASE mycoin_db OWNER mycoin;
```

`CREATEDB` lets Django create its isolated test database when you run the test suite.

### 4. Configure environment variables

Copy the example file:

```bash
cp .env.example .env
```

On Windows, use:

```powershell
Copy-Item .env.example .env
```

Update `.env` with the PostgreSQL values you created:

```env
SECRET_KEY=replace-with-a-random-local-secret
DEBUG=True
DB_NAME=mycoin_db
DB_USER=mycoin
DB_PASSWORD=choose-a-local-password
DB_HOST=localhost
DB_PORT=5432
```

Generate a local `SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 5. Migrate and start the application

```bash
python manage.py migrate
python manage.py check
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## Running tests

Run the complete test suite:

```bash
python manage.py test
```

Run only blockchain and mining tests:

```bash
python manage.py test blockchain
```

The tests cover wallet creation, signing and signature validation, transaction validation, proof-of-work, duplicate-processing protection, atomic settlement, chain linking, tampering detection, explorer pages, and the responsive dashboard flow.

## How the transaction flow works

1. A user registers and automatically receives a wallet with an RSA public/private key pair.
2. The sender enters a recipient wallet address and an MYC amount.
3. MyCoin creates a SHA-256 transaction hash, signs it with the sender's private key, verifies it with the public key, and stores the transaction as `Pending`.
4. A miner selects eligible pending transactions and searches for a nonce whose block hash starts with `000`.
5. The app stores the valid block, links it to the previous block, confirms the transactions, updates the wallet balances, and gives the miner the configured reward in a single database transaction.
6. The explorer displays the confirmed block and transaction. Blockchain validation recalculates hashes and checks the links to detect modifications.

## Demonstration guide

1. Register Alice and Bob in separate browser sessions.
2. Open Bob's wallet and copy its address.
3. As Alice, open **Mine Block** and mine an empty block. Alice receives the default 10 MYC reward.
4. As Alice, open **Send Coins**, transfer 4 MYC to Bob, and show the `Pending` transaction.
5. As Bob, open **Mine Block** and mine the pending transfer. Alice's balance becomes 6 MYC. Bob receives 4 MYC plus the 10 MYC mining reward.
6. Open **Blockchain Explorer**, inspect the latest block and confirmed transaction, then select **Validate Blockchain**.

## Configuration

- The simulated mining reward is `10.00000000` MYC. Change `MINING_REWARD` in `mycoin/settings.py` to adjust it.
- The proof-of-work target is three leading zeros. Change `PROOF_PREFIX` in `blockchain/models.py` only for a local demonstration.

## Upgrading from Phase 4

Run `python manage.py migrate` against the existing database. The migration preserves the Genesis Block and existing signed pending transactions. Development blocks created with the old pre-mining helper fail validation because they do not contain proof-of-work metadata.

## Important note

MyCoin is a centrally hosted educational simulation. It has no peer-to-peer networking, external blockchain integration, cryptocurrency exchange, or real-money functionality.
