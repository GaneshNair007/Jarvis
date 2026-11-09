function getCart(){return JSON.parse(localStorage.getItem('cart')||'[]')}
function saveCart(c){localStorage.setItem('cart',JSON.stringify(c));updateCount()}
function updateCount(){const c=getCart();document.getElementById('cartcount').textContent=c.length?`(${c.reduce((s,i)=>s+i.qty,0)})`:''}
function addToCart(id,name,price){const c=getCart();const f=c.find(i=>i.id===id);if(f)f.qty++;else c.push({id,name,price,qty:1});saveCart(c)}
updateCount();
