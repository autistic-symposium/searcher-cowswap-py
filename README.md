# ✨🐮 CoW Arbitrage Solver 👾✨ 

<br>

**This program implements a solver running arbitrage strategies for the [CoW Swap protocol](https://github.com/cowprotocol).**

<br>

> *[Solvers](https://docs.cow.fi/off-chain-services/solvers) are a key component in the Cow Protocol, serving as the matching engines that find the best execution paths for user orders*.



<br>

---

## Strategies


#### Spread trades

* One-leg limit price arbitrage trade.
* Two-legs limit price arbitrage trade for multiple execution paths.

<br>


---

## Implemented features 


#### Liquidity sources

* Support for constant-product AMMs, such as Uniswap V2 (and its forks). An Uniswap pool is represented by two token balances.



#### Orders types


* Support for single order instances (limit price orders).
* Support for multiple orders on a single token pairs instance.
* Support for multiple orders on multiple token pairs instances.




<br>




---


## Execution specs





> A limit order is an order to buy or sell with a restriction on the maximum price to be paid or the minimum price to be received (the "limit price").

This limit determines when an order can be executed:

```
limit_price = sell_amount / buy_amount >= executed_buy_amount / executed_sell_amount
```

#### Surplus

For multiple execution paths (liquidity sources), we choose the best solution by maximizing the *surplus* of an order:

```
surplus = exec_buy_amount  - exec_sell_amount / limit_price
```

#### Amounts representation

All amounts are expressed by non-negative integer numbers, represented in atoms (i.e., multiples of 10^18). We add `_` to results to denote decimal position, allowing easier reading.

---

## Order specs

User orders describe a trading intent.

#### User order specs

* `sell_token`: token to be sold (added to the amm pool).
* `buy_token`: token to be bought (removed from the amm pool).
* `allow_partial_fill`: if `False`, only fill-or-kill orders are executed.
* `sell_amount`: limit amount for tokens to be sold.
* `buy_amount`: limit amount for tokens to be bought.
* `exec_sell_amount`: how many tokens get sold after order execution.

<br>

#### AMM exec specs


* `amm_exec_buy_amount`: how many tokens the amm "buys" (gets) from the user, and it's the sum of all `exec_sell_amount` amounts of each path (leg) in the order execution.
* `amm_exec_sell_amount`: how many tokens the amm "sells" (gives) to the user, and it's the sum of all `exec_buy_amount` amounts of each path (leg) in the order execution.
* `market_price`: the price to buy a token through the user order specs.
* `prior_price`: the buy price of a token in the reserve prior to being altered by the order.
* `prior_sell_token_reserve`: the initial reserve amount of the "sell" token, prior to being altered by the order.
* `prior_buy_token_reserve`: the initial reserve amount of the "buy" token, prior to being altered by the order.
* `updated_sell_token_reserve`: the reserve amount of the "sell" token after being altered by the order.
* `updated_buy_token_reserve`: the reserve amount of the "buy" token after being altered by the order.


<br>


---

## Installing

#### Install Requirements


```sh
python3 -m venv venv
source ./venv/bin/activate
make install_deps
```

<br>

#### Create an `.env`


```sh
cp .env.sample .env
vim .env
```

<br>

#### Install cowsol

```sh
make install
```

Test your installation:

```
cowsol
```


<br>

---

## Usage


#### Solving a spread trade

```
cowsol -s <order file>
```
<br>


Example output (logging set to `DEBUG`):

```
✅ Solving orders/instance_2.json with spread strategy.
✅ FIRST LEG trade overview:
✅ ➖ sell 1000_000000000000000000 of A
✅ ➕ buy some amount of B2
🟨     Surplus: 918_181818181818181818
🟨     Exchange rate: 2.0
🟨     Exec sell amount: 1000_000000000000000000
🟨     Exec buy amount: 1818_181818181818181818
🟨     Prior sell reserve: 10000_000000000000000000
🟨     Initial buy reserve: 20000_000000000000000000
🟨     Updated sell reserve: 11000_000000000000000000
🟨     Updated buy reserve: 18181_818181818181818180
🟨     Can fill?: True
✅ SECOND LEG trade overview:
✅ ➖ sell 1818_181818181818181818 of B2
✅ ➕ buy some amount of C
🟨     Surplus: 81_081081081081081081
🟨     Exchange rate: 0.6666666666666666
🟨     Exec sell amount: 1818_181818181818181818
🟨     Exec buy amount: 1081_081081081081081081
🟨     Prior sell reserve: 15000_000000000000000000
🟨     Initial buy reserve: 10000_000000000000000000
🟨     Updated sell reserve: 16818_181818181818181820
🟨     Updated buy reserve: 8918_918918918918918919
🟨     Can fill?: True
✅ Total order surplus: 999_262899262899262899
✅ Results saved at solutions/solution_2_cowsol.json.
```

<br>

* Input orders are located at `orders/`,
* Solutions are located at `solutions/`.

<br>

For example, this user order instance

```
{
    "orders": {
        "0": {
            "sell_token": "A",
            "buy_token": "C",
            "sell_amount": "1000_000000000000000000",
            "buy_amount": "900_000000000000000000",
            "allow_partial_fill": false,
            "is_sell_order": true
        }
    },
    "amms": {
        "AC": {
            "reserves": {
                "A": "10000_000000000000000000",
                "C": "10000_000000000000000000"
            }
        }
    }
}

```

would generate the following solution

```
{
    "amms": {
        "AC": {
            "sell_token": "C",
            "buy_token": "A",
            "exec_buy_amount": "1000_000000000000000000",
            "exec_sell_amount": "909_090909090909090909"
        }
    },
    "orders": {
        "0": {
            "allow_partial_fill": false,
            "is_sell_order": true,
            "buy_amount": "900_000000000000000000",
            "sell_amount": "1000_000000000000000000",
            "buy_token": "C",
            "sell_token": "A",
            "exec_buy_amount": "909_090909090909090909",
            "exec_sell_amount": "1000_000000000000000000"
        }
    }
}
```



and this user order instance

<br>

```
{
    "orders": {
        "0": {
            "sell_token": "A",
            "buy_token": "C",
            "sell_amount": "1000_000000000000000000",
            "buy_amount": "900_000000000000000000",
            "allow_partial_fill": false,
            "is_sell_order": true
        }
    },
    "amms": {
        "AB2": {
            "reserves": {
                "A": "10000_000000000000000000",
                "B2": "20000_000000000000000000"
            }
        },        
        "B2C": {
            "reserves": {
                "B2": "15000_000000000000000000",
                "C": "10000_000000000000000000"
            }
        }
    }
}
```

<br>

generates this solution

```
{
    "amms": {
        "AB2": {
            "sell_token": "B2",
            "buy_token": "A",
            "exec_buy_amount": "1000_000000000000000000",
            "exec_sell_amount": "1818_181818181818181818"
        },
        "B2C": {
            "sell_token": "C",
            "buy_token": "B2",
            "exec_buy_amount": "1818_181818181818181818",
            "exec_sell_amount": "1081_081081081081081081"
        }
    },
    "orders": {
        "0": {
            "allow_partial_fill": false,
            "is_sell_order": true,
            "buy_amount": "900_000000000000000000",
            "sell_amount": "1000_000000000000000000",
            "buy_token": "C",
            "sell_token": "A",
            "exec_buy_amount": "1081_081081081081081081",
            "exec_sell_amount": "1000_000000000000000000"
        }
    }
}
```

<br>

#### Listing available amms in an order instance file

```
cowsol -a <order file>
```
<br>

Example output:

```
✅ AMMs available for orders/instance_1.json

{   'AC': {   'reserves': {   'A': '10000_000000000000000000',
                              'C': '10000_000000000000000000'}}}
```

<br>

#### Listing orders in an order instance file

```
cowsol -o <order file>
```

<br>

Example output:

```
✅ Orders for orders/instance_1.json

{   '0': {   'allow_partial_fill': False,
             'buy_amount': '900_000000000000000000',
             'buy_token': 'C',
             'is_sell_order': True,
             'sell_amount': '1000_000000000000000000',
             'sell_token': 'A'}}
```


<br>

----

## Features to be added

* Add support for concurrence (`async`).
* Implement support for AMM fees.
* Add cyclic arbitrage detection.
* Add balancer weighted pools.
* Add stable pools.
* Implement other sources of liquidity.
* Finish implementing and test end-to-end **buy** limit orders.
* Add support for 3 or more legs.
* Add unit tests.



<br>


---

## Resources

* [cow.fi](http://cow.fi/)
* [In-depth solver specification](https://docs.cow.fi/off-chain-services/in-depth-solver-specification)