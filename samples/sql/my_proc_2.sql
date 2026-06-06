CREATE PROCEDURE dbo.usp_ProcessOrderBatch
    @BatchID INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CurrentOrderID INT;
    DECLARE @OrderQueue TABLE (OrderID INT PRIMARY KEY);

    INSERT INTO @OrderQueue (OrderID)
    SELECT OrderID FROM dbo.Orders WHERE BatchID = @BatchID;

    BEGIN TRY
        WHILE EXISTS (SELECT 1 FROM @OrderQueue)
        BEGIN
            SELECT TOP 1 @CurrentOrderID = OrderID FROM @OrderQueue;

            UPDATE dbo.Orders
            SET OrderStatus = 'Processed',
                ProcessedDate = GETDATE()
            WHERE OrderID = @CurrentOrderID;

            UPDATE dbo.OrderItems
            SET LineStatus = 'Processed'
            WHERE OrderID = @CurrentOrderID;

            UPDATE dbo.Inventory
            SET StockQuantity = StockQuantity - 1
            WHERE ProductID IN (
                SELECT ProductID FROM dbo.OrderItems WHERE OrderID = @CurrentOrderID
            );

            DELETE FROM @OrderQueue WHERE OrderID = @CurrentOrderID;
        END

    END TRY
    BEGIN CATCH
        THROW;
    END CATCH

    INSERT INTO dbo.ErrorLog (BatchID, MessageText, CreatedDate)
    VALUES (@BatchID, 'Batch completed', GETDATE());
END
