import smartpy as sp

# Error_message class is used to generate error messages throughout the contract
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

# Kraznik_error_message is a class used to generate error messages specific to the Kraznik NFT contract
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

# Ledger_key class is used to store the mapping between owner addresses and token IDs
class Ledger_key:
    def get_type(self):
        return sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(("owner", "token_id"))

    def make(self, owner, token_id):
        return sp.set_type_expr(sp.record(owner=owner, token_id=token_id), self.get_type())

#Balance_of class is used to handle all calls made to query the token balances of addresses
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

#Attributes contains the list of traits, along with their values and rarities
class Attributes:
    def get_type(self):
        return sp.TRecord(name=sp.TString, value=sp.TString, rarity=sp.TNat)
    def make(self, attributes):
        attributes_list = sp.local("Attributes_List", sp.list(l=[], t=self.get_type()))
        sp.for attr in attributes:
            attributes_list.value.push(attr)
        return attributes_list.value



#Tags contains the list of tags that describe the subject or content of the asset.
class Tags:
    def get_type(self):
        return sp.TList(t=sp.TString)
    def make(self, tags):
        return sp.set_type_expr(tags, self.get_type())

# Token metadata containing the following fields - 
# 1. Token id
# 2. Description
# 3. Date
# 4. Tags
# 5. Artifact URI
# 6. Attributes
class Token_meta_data:
    def get_type(self):
        attributes_inst = Attributes()
        tags_inst = Tags()
        return sp.TRecord(token_id=sp.TNat, description=sp.TString, date=sp.TTimestamp, artifactUri=sp.TString, tags=tags_inst.get_type(), attributes=sp.TList(attributes_inst.get_type()))
    def make(self, token_metadata):
        return sp.set_type_expr(token_metadata, self.get_type())

#KraznikCollections is the core contract in the application - Consists of an ownership ledger, token_meta_data map
class KraznikCollections(sp.Contract):
    def __init__(self, metadata, admin):
        self.ledger_key = Ledger_key()
        self.error_message = Error_message()
        self.kraznik_error_message = Kraznik_error_message()
        self.token_meta_data = Token_meta_data()
        self.init(
            ledger=sp.big_map(tkey=self.ledger_key.get_type(), tvalue=sp.TNat),
            paused=False,
            administrator=admin,
            metadata=metadata,      #Core Contract Metadata
            all_tokens=sp.set(t=sp.TNat),
            tokens = sp.big_map(tkey=sp.TNat, tvalue=self.token_meta_data.get_type()),
            MAX_SUPPLY=10000,       #Maximum supply quantity of the NFTs
            MAX_PURCHASE=2,         #Maximum purchase allowed for each user
            AMOUNT_RESERVED=100,    #Number of NFTs reserved for the team members
            MINT_PRICE=sp.tez(69),  #Initial mint price of the NFTs (in XTZ)
            RENAME_PRICE=sp.tez(1), #Price needed to rename the NFTs
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

    #Function to "mint" an NFT - verifies that the contract is not paused
    @sp.entry_point
    def mint(self, tokens_metadata, purchase_quantity):
        sp.verify(~self.is_paused(), self.error_message.paused())
        
        #Sets the type for the "purchase quantity" and "token metadata" for multiple tokens
        sp.set_type(tokens_metadata, sp.TList(self.token_meta_data.get_type()))
        sp.set_type(purchase_quantity, sp.TNat)

        # token_id starting from 0-9999
        token_id = sp.len(self.data.all_tokens)
        
        sp.verify(purchase_quantity > 0)
        sp.verify(sp.len(tokens_metadata) == purchase_quantity,
                  message=self.kraznik_error_message.invalid())
        sp.verify(purchase_quantity <= self.data.MAX_PURCHASE,
                  message=self.kraznik_error_message.cant_purchase_more())
        sp.verify(token_id + purchase_quantity <= self.data.MAX_SUPPLY,
                  message=self.kraznik_error_message.exceeded_max_supply())
        sp.verify(sp.amount == sp.mul(purchase_quantity, self.data.MINT_PRICE),
                  message=self.kraznik_error_message.insufficient_amount_paid())
        sp.for token_metadata in tokens_metadata:
            token_id = sp.len(self.data.all_tokens)
            user = self.ledger_key.make(sp.sender, token_id)
            self.data.ledger[user] = 1
            #Compute hash of metadata object and check if hash of token_metadata exsist
            self.data.tokens[token_id] = self.token_meta_data.make(token_metadata)
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
    tags = sp.list(l = ["tag1","tag2"])
    attributes = [sp.record(name="colour",value="Blue",rarity=100)]
    tok0_md = sp.record(token_id=0, description=sp.string("Kangaroo"), artifactUri=sp.string("ipfsURL"), date=sp.timestamp(1630402450),tags=tags, attributes=attributes)
    c1.mint(
        tokens_metadata = [tok0_md],
        purchase_quantity = 1
    ).run(sender = alice, amount = sp.tez(69), valid = True)

    ## Alice mints again, token_id = 1 is minted with same tok0_md
    ## metadata needs to be different, someone can exploit using similar metadata, or any metadata
    # c1.mint(
    #     token_metadatas = sp.list([tok0_md]),
    #     purchase_quantity = 1
    # ).run(sender = alice, amount = sp.tez(69), valid = True)

    # scenario.p("Bob mints 2 token - token_id = 1,2")
    # tok1_md = KraznikCollections.make_metadata(
    #     name = "Kangaroo1",
    #     symbol = "Kq1",
    #     tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    # )
    # tok2_md = KraznikCollections.make_metadata(
    #     name = "Kangaroo2",
    #     symbol = "Kq2",
    #     tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    # )
    # c1.mint(
    #     token_metadatas = sp.list([tok1_md, tok2_md]),
    #     purchase_quantity = 2
    # ).run(sender = bob, amount = sp.tez(69*2), valid = True)

    # scenario.p("Alice mints 2 token, with - token_id = 3,4, she already has token_id = 0")
    # tok3_md = KraznikCollections.make_metadata(
    #     name = "Kangaroo1",
    #     symbol = "Kq1",
    #     tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    # )
    # tok4_md = KraznikCollections.make_metadata(
    #     name = "Kangaroo2",
    #     symbol = "Kq2",
    #     tokenUri = "ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG"
    # )
    # c1.mint(
    #     token_metadatas = sp.list([tok3_md, tok4_md]),
    #     purchase_quantity = 2
    # ).run(sender = alice, amount = sp.tez(69*2), valid=True)

    # scenario.p("Alice mints 2 token, but do not send right amount of tez, with - token_id = 3,4")
    # c1.mint(
    #     token_metadatas = sp.list([tok3_md, tok4_md]),
    #     purchase_quantity = 2
    # ).run(sender = alice, amount = sp.tez(69), valid=False)

    # scenario.p("Alice mints 2 token, with token_metadatas length != purchase_quantity, should be invalid - token_id = 3,4")
    # c1.mint(
    #     token_metadatas = sp.list([tok3_md]),
    #     purchase_quantity = 2
    # ).run(sender = alice, amount = sp.tez(69), valid=False)

    # scenario.p("Bob try to mint 3 tokens in one txn, should fail")
    # c1.mint(
    #     token_metadatas = sp.list([tok2_md, tok3_md, tok4_md]),
    #     purchase_quantity = 3
    # ).run(sender = alice, amount = sp.tez(69*3), valid=False)
    
