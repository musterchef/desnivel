'use strict';
document.getElementById('skin').addEventListener('change', event => {
  document.documentElement.dataset.skin = event.target.value;
});
