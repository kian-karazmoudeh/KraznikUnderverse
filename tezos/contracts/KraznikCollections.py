import smartpy as sp


class Error_message:
    def __init__(self):
        self.prefix = "FA2_"

    def make(self, s): return (self.prefix + s)
    def token_undefined(self): return self.make("TOKEN_UNDEFINED")
    def insufficient_balance(self): return self.make("INSUFFICIENT_BALANCE")
    def not_operator(self): return self.make("NOT_OPERATOR")
    def not_owner(self): return self.make("NOT_OWNER")
    def operators_unsupported(self): return self.make("OPERATORS_UNSUPPORTED")
    def not_admin(self): return self.make("NOT_ADMIN")
    def not_admin_or_operator(self): return self.make("NOT_ADMIN_OR_OPERATOR")
    def paused(self): return self.make("PAUSED")


class Kraznik_error_message:
    def __init__(self):
        self.prefix = "Kraznik_"

    def make(self, s): return (self.prefix + s)

    def cant_purchase_more(self): return self.make(
        "CANT_PURCHASE_MORE_THAN_MAX_PURCHASE_ALLOWED")

    def exceeded_max_supply(self): return self.make("EXCEEDED_MAX_SUPPLY")

    def insufficient_amount_paid(self): return self.make(
        "INSUFFICIENT_AMOUNT_PAID")

    def invalid(self): return self.make("INVALID")


# The current type for a batched transfer in the specification is as
# follows:
##
# ```ocaml
# type transfer = {
##   from_ : address;
# txs: {
##     to_ : address;
##     token_id : token_id;
##     amount : nat;
# } list
# } list
# ```
##
# This class provides helpers to create and force the type of such elements.
# It uses the `FA2_config` to decide whether to set the right-comb layouts.


class Batch_transfer:
    def __init__(self, config):
        self.config = config

    def get_transfer_type(self):
        tx_type = sp.TRecord(to_=sp.TAddress,
                             token_id=sp.TNat,
                             amount=sp.TNat)
        if self.config.force_layouts:
            tx_type = tx_type.layout(
                ("to_", ("token_id", "amount"))
            )
        transfer_type = sp.TRecord(from_=sp.TAddress,
                                   txs=sp.TList(tx_type)).layout(
                                       ("from_", "txs"))
        return transfer_type

    def get_type(self):
        return sp.TList(self.get_transfer_type())

    def item(self, from_, txs):
        v = sp.record(from_=from_, txs=txs)
        return sp.set_type_expr(v, self.get_transfer_type())

# The class `Ledger_key` defines the key type for the main ledger (big-)map:
##
# - In *“Babylon mode”* we also have to call `sp.pack`.
# - In *“single-asset mode”* we can just use the user's address.


class Ledger_key:
    def get_type(self):
        return sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(("owner", "token_id"))

    def make(self, owner, token_id):
        return sp.set_type_expr(sp.record(owner=owner, token_id=token_id), self.get_type())


class Balance_of:
    def request_type():
        return sp.TRecord(
            owner=sp.TAddress,
            token_id=sp.TNat).layout(("owner", "token_id"))

    def response_type():
        return sp.TList(
            sp.TRecord(
                request=Balance_of.request_type(),
                balance=sp.TNat).layout(("request", "balance")))

    def entry_point_type():
        return sp.TRecord(
            callback=sp.TContract(Balance_of.response_type()),
            requests=sp.TList(Balance_of.request_type())
        ).layout(("requests", "callback"))


class Token_meta_data:
    def get_type():
        return sp.TRecord(token_id=sp.TNat, token_info=sp.TMap(sp.TString, sp.TBytes)).layout(("token_id", "token_info"))


class Token_value:
    def get_type(self):
        return sp.TRecord(
            name=sp.TString,
            description=sp.TString,
            tokenUri=sp.TString
        )


class KraznikCollections(sp.Contract):
    def __init__(self, metadata, admin):
        self.ledger_key = Ledger_key()
        self.error_message = Error_message()
        self.kraznik_error_message = Kraznik_error_message()
        self.init(
            ledger=sp.big_map(tkey=self.ledger_key.get_type(), tvalue=sp.TNat),
            token_meta_data=sp.big_map(
                tkey=sp.TNat, tvalue=Token_meta_data.get_type()),
            paused=False,
            administrator=admin,
            metadata=metadata,  # contract metadata
            all_tokens=sp.set(t=sp.TNat),
            # Token_value should follow the TZIP-21 standard
            # tokens=sp.big_map(tkey=sp.TNat, tvalue=Token_value.get_type()),
            MAX_SUPPLY=10000,
            MAX_PURCHASE=2,
            AMOUNT_RESERVED=100,  # for team members
            MINT_PRICE=sp.tez(69),
            RENAME_PRICE=sp.tez(1),  # we can make the first rename free
        )

    def is_administrator(self, sender):
        return sender == self.data.administrator

    @sp.entry_point
    def set_administrator(self, params):
        sp.verify(self.is_administrator(sp.sender),
                  message=self.error_message.not_owner())
        self.data.administrator = params

    def is_paused(self):
        return self.data.paused

    @sp.entry_point
    def set_pause(self, params):
        sp.verify(self.is_administrator(sp.sender),
                  message=self.error_message.not_owner())
        self.data.paused = params

    def make_metadata(name, symbol, tokenUri):
        "Helper function to build metadata JSON bytes values."
        return (sp.map(
            l={
                "name": sp.utils.bytes_of_string(name),
                "symbol": sp.utils.bytes_of_string(symbol),
                # "decimals": sp.utils.bytes_of_string("%d" % decimals),
                "tokenUri": sp.utils.bytes_of_string(tokenUri)
            },
            # tkey=sp.TString,
            # tvalue=sp.TString
        ))

    @sp.entry_point
    def mint(self, token_metadatas, purchase_quantity):
        sp.verify(~self.is_paused(), self.error_message.paused())
        # anyone can mint the tokens

        sp.set_type(token_metadatas, sp.TList(sp.TMap(sp.TString, sp.TBytes)))
        sp.set_type(purchase_quantity, sp.TNat)

        # token_id starting from 0-9999
        token_id = sp.len(self.data.all_tokens)
        
        sp.verify(purchase_quantity > 0)
        sp.verify(sp.len(token_metadatas) == purchase_quantity,
                  message=self.kraznik_error_message.invalid())
        sp.verify(purchase_quantity <= self.data.MAX_PURCHASE,
                  message=self.kraznik_error_message.cant_purchase_more())
        sp.verify(token_id + purchase_quantity <= self.data.MAX_SUPPLY,
                  message=self.kraznik_error_message.exceeded_max_supply())
        sp.verify(sp.amount == sp.mul(purchase_quantity, self.data.MINT_PRICE),
                  message=self.kraznik_error_message.insufficient_amount_paid())

        sp.for token_metadata in token_metadatas:
            token_id = sp.len(self.data.all_tokens)
            user = self.ledger_key.make(sp.sender, token_id)
            self.data.ledger[user] = 1  # non-fungible
            self.data.token_meta_data[token_id] = sp.record(
                token_id=token_id, token_info=token_metadata
            )
            # self.data.tokens[token_id] = sp.record(

            # )
            self.data.all_tokens.add(token_id)

        # we have to add tokenUri to the token metadata => TZIP-21
        # we have to make assignment of tokenUris to tokenIds random (frontend)
        # rather than non-consecutive minting of token-ids


@sp.add_test(name="Demo")
def test():
    scenario = sp.test_scenario()
    scenario.h1("FA2 Contract name: " + "KraznikCollections")
    scenario.table_of_contents()
    admin = sp.test_account("Administrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Bob")

    scenario.h2("Accounts")
    scenario.show([admin, alice, bob])
    c1 = KraznikCollections(
        metadata=sp.utils.metadata_of_url("https://example.com"),
        admin=admin.address
    )
    scenario += c1
    scenario.h2("Initial minting")
    scenario.p("Alice mints 1 token - token_id=0")
    tok0_md = KraznikCollections.make_metadata(
        name = "Kangaroo0",
        symbol = "Kq0",
        tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    )
    c1.mint(
        token_metadatas = sp.list([tok0_md]),
        purchase_quantity = 1
    ).run(sender = alice, amount = sp.tez(69), valid = True)

    ## Alice mints again, token_id = 1 is minted with same tok0_md
    ## metadata needs to be different, someone can exploit using similar metadata, or any metadata
    # c1.mint(
    #     token_metadatas = sp.list([tok0_md]),
    #     purchase_quantity = 1
    # ).run(sender = alice, amount = sp.tez(69), valid = True)

    scenario.p("Bob mints 2 token - token_id = 1,2")
    tok1_md = KraznikCollections.make_metadata(
        name = "Kangaroo1",
        symbol = "Kq1",
        tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    )
    tok2_md = KraznikCollections.make_metadata(
        name = "Kangaroo2",
        symbol = "Kq2",
        tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    )
    c1.mint(
        token_metadatas = sp.list([tok1_md, tok2_md]),
        purchase_quantity = 2
    ).run(sender = bob, amount = sp.tez(69*2), valid = True)

    scenario.p("Alice mints 2 token, with - token_id = 3,4, she already has token_id = 0")
    tok3_md = KraznikCollections.make_metadata(
        name = "Kangaroo1",
        symbol = "Kq1",
        tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    )
    tok4_md = KraznikCollections.make_metadata(
        name = "Kangaroo2",
        symbol = "Kq2",
        tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    )
    c1.mint(
        token_metadatas = sp.list([tok3_md, tok4_md]),
        purchase_quantity = 2
    ).run(sender = alice, amount = sp.tez(69*2), valid=True)

    scenario.p("Alice mints 2 token, but do not send right amount of tez, with - token_id = 3,4")
    c1.mint(
        token_metadatas = sp.list([tok3_md, tok4_md]),
        purchase_quantity = 2
    ).run(sender = alice, amount = sp.tez(69), valid=False)

    scenario.p("Alice mints 2 token, with token_metadatas length != purchase_quantity, should be invalid - token_id = 3,4")
    c1.mint(
        token_metadatas = sp.list([tok3_md]),
        purchase_quantity = 2
    ).run(sender = alice, amount = sp.tez(69), valid=False)

    scenario.p("Bob try to mint 3 tokens in one txn, should fail")
    c1.mint(
        token_metadatas = sp.list([tok2_md, tok3_md, tok4_md]),
        purchase_quantity = 3
    ).run(sender = alice, amount = sp.tez(69*3), valid=False)
    
