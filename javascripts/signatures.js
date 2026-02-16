// Add function signatures to content areas
document.addEventListener('DOMContentLoaded', function() {
    // Find all function containers
    const functionContainers = document.querySelectorAll('.doc.doc-object.doc-function, .doc-contents > .doc:not(.doc-children)');
    
    functionContainers.forEach(container => {
        // Find the function header with signature
        const header = container.querySelector('.doc-heading, h3.doc-heading');
        const codeElement = header ? header.querySelector('code') : null;
        
        if (codeElement) {
            // Extract the signature text
            const signatureText = codeElement.textContent.trim();
            
            // Find the content area
            const contentArea = container.querySelector('.doc-content');
            
            if (contentArea && signatureText) {
                // Check if signature block already exists
                const existingSignature = contentArea.querySelector('.custom-signature-block');
                if (!existingSignature) {
                    // Create signature block
                    const signatureBlock = document.createElement('div');
                    signatureBlock.className = 'custom-signature-block';
                    signatureBlock.textContent = signatureText;
                    
                    // Insert at the beginning of content area
                    contentArea.insertBefore(signatureBlock, contentArea.firstChild);
                }
            }
        }
    });
}); 