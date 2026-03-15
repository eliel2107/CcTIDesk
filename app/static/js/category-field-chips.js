(function () {
  function setGroupState(group, checked) {
    group.querySelectorAll('.field-chip-input[type="checkbox"]').forEach(function (input) {
      input.checked = checked;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  function bindGroup(group) {
    var checkAllButton = group.querySelector('[data-chip-action="check-all"]');
    var clearAllButton = group.querySelector('[data-chip-action="clear-all"]');

    if (checkAllButton) {
      checkAllButton.addEventListener('click', function () {
        setGroupState(group, true);
      });
    }

    if (clearAllButton) {
      clearAllButton.addEventListener('click', function () {
        setGroupState(group, false);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-field-chip-group]').forEach(bindGroup);
  });
})();
