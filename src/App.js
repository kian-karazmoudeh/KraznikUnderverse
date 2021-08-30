import './App.css';
import { MichelsonMap, TezosToolkit } from '@taquito/taquito';
import { BeaconWallet } from '@taquito/beacon-wallet';
import { BeaconEvent, defaultEventCallbacks } from '@airgap/beacon-sdk';
import { useEffect, useState } from 'react';

import { char2Bytes } from '@taquito/utils';

// https://testnet-tezos.giganode.io
const Tezos = new TezosToolkit('https://florencenet.api.tez.ie');
const options = {
    name: 'KraznikUnderverse',
    disableDefaultEvents: true,
    iconUrl: 'https://tezostaquito.io/img/favicon.png',
    preferredNetwork: 'florencenet',
    eventHandlers: {
        // To keep the pairing alert, we have to add the following default event handlers back
        [BeaconEvent.PAIR_INIT]: {
            handler: defaultEventCallbacks.PAIR_INIT,
        },
        [BeaconEvent.PAIR_SUCCESS]: {
            handler: defaultEventCallbacks.PAIR_SUCCESS,
        },
        PERMISSION_REQUEST_SUCCESS: {
            handler: async (data) => {
                console.log('permission data:', data);
            },
        },
    },
};

const wallet = new BeaconWallet(options);
Tezos.setWalletProvider(wallet);

const contractAddress = 'KT1C6bQhy4gSSt3HYd1E6xUoHV5ZMUbkRY38';

const App = () => {
    const [userAddress, setUserAddress] = useState('');
    const [balance, setBalance] = useState('');
    const [contractInstance, setContractInstance] = useState(null);
    const [contractStorage, setContractStorage] = useState('');
    const [purchaseQuantity, setPurchaseQuantity] = useState(0);

    const onConnectWallet = async () => {
        await wallet.requestPermissions({
            network: {
                // type: 'mainnet' | 'florencenet' | 'granadanet' | 'custom',
                type: 'florencenet',
            },
        });
        const userAddress = await wallet.getPKH();
        setUserAddress(userAddress);
        Tezos.setWalletProvider(wallet);
    };

    useEffect(() => {
        // Tezos.setWalletProvider(wallet);
        async function walletConnected() {
            const activeAccount = await wallet.client.getActiveAccount();
            if (activeAccount) {
                setUserAddress(activeAccount.address);
                const balance = await Tezos.tz.getBalance(
                    activeAccount.address
                );
                console.log('balance: ', balance.toString());
                if (balance) setBalance(balance.toString());
                if (activeAccount) {
                    console.log('Already connected: ', activeAccount.address);
                }
            }
        }
        walletConnected();
    }, [userAddress]);

    useEffect(() => {
        async function contractData() {
            // contract instance
            const contract = await Tezos.wallet.at(contractAddress);
            setContractInstance(contract);
            const storage = await contract.storage();
            setContractStorage(storage);
            console.log('storage: ', storage);
            // console.log(Tezos);
            // let name = 'kangroo1',
            //     symbol = 'Kg1',
            //     tokenUri = 'ipfs://Qkjdncmdcs..';
            // const tok_md = await contract.methods.make_metadata(
            //     name,
            //     symbol,
            //     tokenUri
            // );
            // console.log('token metadta: ', tok_md);
        }

        contractData();
    }, []);

    const onMint = async () => {
        try {
            console.log('Minting..');
            let token_metadatas = [];
            let tokens = contractStorage.all_tokens.length;
            let pq = purchaseQuantity;
            while (pq--) {
                let token_md = MichelsonMap.fromLiteral({
                    name: char2Bytes(`Kangroo${tokens}`),
                    symbol: char2Bytes(`Kg${tokens}`),
                    tokenUri: char2Bytes(
                        'ipfs://QmV3a1TAdCncfs84Gi9msDsDJVQBDt6Wb5gJRVuFRfrgtG'
                    ),
                });

                token_metadatas.push(token_md);
                tokens++;
            }
            // let purchaseQuantity = 2;
            let priceToPay =
                (contractStorage.MINT_PRICE.toString() * purchaseQuantity) /
                10 ** 6;

            console.log(token_metadatas);
            console.log(tokens);
            console.log(priceToPay);
            console.log(purchaseQuantity);
            const op = await contractInstance.methods
                .mint(purchaseQuantity, token_metadatas)
                .send({
                    amount: priceToPay,
                });

            await op.confirmation();

            console.log('Minted Succesfully');
            window.location.reload();
        } catch (err) {
            alert('Please try again after 50 seconds');
            console.log(err);
        }
    };

    // const onSend = async () => {
    //     const op = await Tezos.wallet
    //         .transfer({
    //             to: 'tz1ZA9ttp6QpPFQoNKLLqgbezcQ5kqQHt5BA',
    //             amount: 0.2,
    //         })
    //         .send();

    //     console.log('Hash: ', op.opHash);
    //     const result = await op.confirmation();
    //     if (result.completed) {
    //         console.log('Transaction succesful');
    //     } else {
    //         console.log('Error occured');
    //     }
    // };

    const onDisconnect = async () => {
        // await new Promise((resolve) => setTimeout(resolve, 1000));
        await wallet.clearActiveAccount();
        window.location.reload();
    };

    return (
        <div className="App">
            {userAddress ? (
                <div>
                    <button onClick={onDisconnect}>Disconnect</button>
                    <div>user address: {userAddress}</div>
                    <div>Balance: {balance}</div>
                </div>
            ) : (
                <button onClick={onConnectWallet}>Connect Wallet</button>
            )}
            <div>contract address: {contractAddress}</div>
            {contractInstance ? (
                <div>
                    <input
                        type="number"
                        min="1"
                        step="1"
                        max={
                            contractStorage
                                ? contractStorage.MAX_PURCHASE.toString()
                                : 2
                        }
                        placeholder="Enter the purchase quantity"
                        value={purchaseQuantity}
                        onChange={(e) => setPurchaseQuantity(e.target.value)}
                    />
                    <button onClick={onMint}>Mint</button>
                </div>
            ) : null}
            {contractStorage !== '' ? (
                <div>
                    <div>
                        Max supply : {contractStorage.MAX_SUPPLY.toString()}
                    </div>
                    <div>
                        Max purchase allowed :{' '}
                        {contractStorage.MAX_PURCHASE.toString()}
                    </div>
                    <div>
                        mint price for 1 kangroo:{' '}
                        {contractStorage.MINT_PRICE.toString() / 10 ** 6} XTZ
                    </div>
                    <div>
                        number of tokens minted yet:{' '}
                        {contractStorage.all_tokens.length}
                    </div>
                    <div></div>
                </div>
            ) : null}
        </div>
    );
};

export default App;
