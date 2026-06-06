-- Sample: enterprise-style procedure for harness / inventory testing
-- Exercises: GO batches, revision block comment, TRY/CATCH + transaction, IF/ELSE,
-- WHILE, table variables, JOIN UPDATE, MERGE, mixed semicolon style.

IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[usp_ComplexOrderSettlement]') AND type IN (N'P', N'PC'))
    DROP PROCEDURE [dbo].[usp_ComplexOrderSettlement];
GO

SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO


/*
================================================================================
 Object:     dbo.usp_ComplexOrderSettlement
 Purpose:    Settle a batch of orders with inventory and audit side effects
--------------------------------------------------------------------------------
 Mod Date     Modified By     Description
 -----------  --------------  -------------------------------------------------
 2023-06-01   platform        Initial release
 2024-11-14   ops             TRY/CATCH + explicit transaction
 2025-02-03   ops             MERGE into SettlementLog; @DryRun branch
================================================================================
*/

CREATE PROCEDURE dbo.usp_ComplexOrderSettlement
    @BatchID INT,
    @DryRun BIT = 0
AS
BEGIN
    SET NOCOUNT ON

    DECLARE @RowCount INT = 0
    DECLARE @CurrentOrderID INT
    -- introducing status variable to track the status of the procedure
    DECLARE @Status NVARCHAR(20) = N'Pending'
    DECLARE @Queue TABLE (
        OrderID INT NOT NULL PRIMARY KEY,
        SortKey INT NOT NULL
    )

    BEGIN TRY
        BEGIN TRANSACTION

        INSERT INTO @Queue (OrderID, SortKey)
        SELECT OrderID, ROW_NUMBER() OVER (ORDER BY OrderID)
        FROM dbo.Orders
        WHERE BatchID = @BatchID
          AND OrderStatus = @Status

        IF @@ROWCOUNT = 0
        BEGIN
            RAISERROR(N'No orders found for batch %d', 16, 1, @BatchID)
            RETURN
        END

        WHILE EXISTS (SELECT 1 FROM @Queue)
        BEGIN
            SELECT TOP 1
                @CurrentOrderID = OrderID
            FROM @Queue
            ORDER BY SortKey

            IF @DryRun = 1
            BEGIN
                SET @RowCount = @RowCount + 1
            END
            ELSE
            BEGIN
                UPDATE dbo.Orders
                SET OrderStatus = N'Settled',
                    SettledDate = GETDATE()
                WHERE OrderID = @CurrentOrderID

                UPDATE i
                SET i.ReservedQty = i.ReservedQty - oi.Quantity
                FROM dbo.Inventory i
                INNER JOIN dbo.OrderItems oi ON oi.ProductID = i.ProductID
                WHERE oi.OrderID = @CurrentOrderID

                /**************
                * Comment block
                *
                * More comment lines
                *
                * Even more comment lines
                *
                * Even more comment lines
                *
                * Even more comment lines
                *
                * Even more comment lines
                *
                * Even more comment lines
                *
                * Even more comment lines
                *
                * Even more comment lines
                *
                * Even more comment lines
                ***************/

                MERGE dbo.SettlementLog AS tgt
                USING (SELECT @CurrentOrderID AS OrderID) AS src
                ON tgt.OrderID = src.OrderID
                WHEN MATCHED THEN
                    UPDATE SET tgt.UpdatedDate = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (OrderID, BatchID, CreatedDate)
                    VALUES (src.OrderID, @BatchID, GETDATE())

                INSERT INTO dbo.AuditLog (EntityId, ActionCode, CreatedDate)
                VALUES (@CurrentOrderID, N'SETTLE', GETDATE())

                SET @RowCount = @RowCount + 1
            END

            DELETE FROM @Queue WHERE OrderID = @CurrentOrderID
        END

        COMMIT TRANSACTION
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION

        INSERT INTO dbo.ErrorLog (BatchID, ErrorMessage, CreatedDate)
        VALUES (@BatchID, ERROR_MESSAGE(), GETDATE())

        SET @Status = N'Failed'
        THROW
    END CATCH
END
GO
